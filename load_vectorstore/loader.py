"""Load and query FAISS vector stores for retrieval-augmented chat.

This module complements :mod:`embedding_app.vector_store` by providing
runtime loading and querying utilities suitable for RAG-style chat
experiences.  It loads a persisted FAISS index alongside document
metadata and exposes a simple search API that embeds incoming queries,
retrieves the nearest neighbours and returns both scores and context
payloads.  Extensive logging is used to aid observability in
production deployments.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise RuntimeError(
        "The faiss library is required for loading vector stores. Install faiss or faiss-cpu via pip or conda."
    ) from exc

from ..config import EmbeddingConfig
from ..embedding_client import EmbeddingClient
from ..utils import setup_logging

logger = logging.getLogger(__name__)
DEFAULT_CACHE_TTL_SECONDS = 60 * 60


@dataclass
class _CacheEntry:
    loader: "VectorStoreLoader"
    last_access: float


class VectorStoreLoader:
    """Load a persisted vector store and perform similarity search."""

    def __init__(
        self,
        store_dir: str,
        *,
        embedding_config: Optional[EmbeddingConfig] = None,
        log_dir: Optional[str] = None,
    ) -> None:
        """Initialise the loader with paths and configuration.

        Parameters
        ----------
        store_dir:
            Path to the directory containing ``index.faiss`` and
            ``metadata.json`` produced by :class:`~embedding_app.vector_store.VectorStoreBuilder`.
        embedding_config:
            Optional :class:`~embedding_app.config.EmbeddingConfig`
            describing the embedding endpoint used to encode query
            text.  When omitted defaults are used.
        log_dir:
            Optional directory for log files.  If provided,
            :func:`~embedding_app.utils.setup_logging` is invoked to
            ensure file+console logging is configured.
        """
        self.store_dir = Path(store_dir)
        self.index_path = self.store_dir / "index.faiss"
        self.metadata_path = self.store_dir / "metadata.json"
        self.embedding_client = EmbeddingClient(embedding_config or EmbeddingConfig())
        self._index: Optional[Any] = None
        self._metadata: List[Dict[str, Any]] = []

        if log_dir and not logging.getLogger().handlers:
            setup_logging(log_dir, logging.INFO)
        logger.debug("VectorStoreLoader initialised for store at %s", self.store_dir)

    @property
    def is_loaded(self) -> bool:
        """Return True when the FAISS index and metadata are in memory."""
        return self._index is not None and bool(self._metadata)

    def load(self) -> None:
        """Load the FAISS index and metadata from disk."""
        start_time = time.perf_counter()
        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {self.index_path}")
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found at {self.metadata_path}")

        logger.info("Loading FAISS index from %s", self.index_path)
        self._index = faiss.read_index(str(self.index_path))

        logger.info("Loading metadata from %s", self.metadata_path)
        with self.metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)

        if not isinstance(metadata, list):
            raise ValueError("metadata.json must contain a list of metadata entries")

        self._metadata = metadata

        # Validate dimensionality and counts
        if self._index.ntotal != len(self._metadata):
            logger.warning(
                "Vector store mismatch: index has %d vectors, metadata contains %d entries",
                self._index.ntotal,
                len(self._metadata),
            )
        elapsed = time.perf_counter() - start_time
        logger.info("Vector store loaded in %.2f seconds", elapsed)

    def _ensure_ready(self) -> None:
        if not self.is_loaded:
            raise RuntimeError("Vector store is not loaded. Call load() first.")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Embed a query and perform similarity search against the index."""
        if not query:
            raise ValueError("Query text must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")

        self._ensure_ready()

        logger.info("Embedding query for retrieval (top_k=%d)", top_k)
        embed_start = time.perf_counter()
        embedding = self.embedding_client.embed_documents([query])
        embed_elapsed = time.perf_counter() - embed_start
        logger.debug("Embedding completed in %.2f seconds", embed_elapsed)

        if not embedding or not embedding[0]:
            raise RuntimeError("Embedding service returned no vectors for the query")

        vector = np.array(embedding[0], dtype="float32").reshape(1, -1)
        if vector.shape[1] != self._index.d:  # type: ignore[union-attr]
            raise ValueError(
                f"Embedding dimension {vector.shape[1]} does not match index dimension {self._index.d}"  # type: ignore[union-attr]
            )

        search_k = min(top_k, self._index.ntotal)  # type: ignore[union-attr]
        logger.info("Running FAISS search for %d neighbours", search_k)
        search_start = time.perf_counter()
        scores, ids = self._index.search(vector, search_k)  # type: ignore[union-attr]
        search_elapsed = time.perf_counter() - search_start
        logger.info("FAISS search completed in %.2f seconds", search_elapsed)

        results: List[Dict[str, Any]] = []
        for idx, score in zip(ids[0], scores[0]):  # type: ignore[index]
            if idx < 0:
                continue
            metadata = self._metadata[idx] if idx < len(self._metadata) else {}
            results.append(
                {
                    "id": int(idx),
                    "score": float(score),
                    "text": metadata.get("text", ""),
                    "metadata": {k: v for k, v in metadata.items() if k != "text"},
                }
            )
        logger.debug("Search returned %d result(s)", len(results))
        return results

    def build_context(self, query: str, top_k: int = 5, separator: str = "\n\n") -> str:
        """Return a concatenated context string for RAG prompts."""
        results = self.search(query, top_k=top_k)
        context_parts = [entry["text"] for entry in results if entry.get("text")]
        context = separator.join(context_parts)
        logger.debug("Built context string with %d chunk(s)", len(context_parts))
        return context


def load_vector_store(
    store_dir: str,
    embedding_config: Optional[EmbeddingConfig] = None,
    log_dir: Optional[str] = None,
) -> VectorStoreLoader:
    """Convenience helper to load a vector store and return the loader.

    This function fully loads the FAISS index and metadata into memory
    and returns a :class:`VectorStoreLoader` instance ready for search.
    """
    logger.info("Loading vector store from %s", store_dir)
    loader = VectorStoreLoader(store_dir, embedding_config=embedding_config, log_dir=log_dir)
    loader.load()
    return loader


class CachedVectorStoreManager:
    """Maintain session-scoped loaders cached with an inactivity TTL."""

    def __init__(
        self,
        store_dir: str,
        *,
        embedding_config: Optional[EmbeddingConfig] = None,
        log_dir: Optional[str] = None,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self.store_dir = store_dir
        self.embedding_config = embedding_config
        self.log_dir = log_dir
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, _CacheEntry] = {}

    def _evict_stale(self) -> None:
        now = time.monotonic()
        expired = [sid for sid, entry in self._cache.items() if now - entry.last_access > self.ttl_seconds]
        for sid in expired:
            logger.info("Evicting cached vector store for session %s after %.0f seconds of inactivity", sid, self.ttl_seconds)
            self._cache.pop(sid, None)

    def _touch(self, session_id: str) -> None:
        if session_id in self._cache:
            self._cache[session_id].last_access = time.monotonic()

    def get_loader(self, session_id: str) -> VectorStoreLoader:
        """Return a cached loader for the session or load a new one."""
        if not session_id:
            raise ValueError("session_id must not be empty")

        self._evict_stale()
        entry = self._cache.get(session_id)
        if entry:
            logger.debug("Reusing cached vector store for session %s", session_id)
            self._touch(session_id)
            return entry.loader

        logger.info("Loading vector store for new session %s", session_id)
        loader = load_vector_store(self.store_dir, embedding_config=self.embedding_config, log_dir=self.log_dir)
        self._cache[session_id] = _CacheEntry(loader=loader, last_access=time.monotonic())
        return loader

    def query(self, session_id: str, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Search using a session-scoped loader and return results/context."""
        loader = self.get_loader(session_id)
        results = loader.search(query, top_k=top_k)
        context = loader.build_context(query, top_k=top_k)
        self._touch(session_id)
        return {"results": results, "context": context}
