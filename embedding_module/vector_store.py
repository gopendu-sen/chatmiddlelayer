"""Utilities for building and persisting FAISS vector stores.

This module encapsulates all interactions with the FAISS library.  It
builds an index from a collection of embeddings and persists both
the index and associated metadata to disk.  FAISS is a library
developed by Meta for efficient similarity search and clustering of
dense vectors.  It provides algorithms that search in sets of
vectors of any size and includes Python bindings for ease of use【508588818496683†L344-L363】.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import numpy as np

try:
    import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise RuntimeError(
        "The faiss library is required for vector store creation. "
        "Install faiss or faiss-cpu via pip or conda."
    ) from exc

from .document import Document
from .utils import ensure_unique_path, setup_logging

logger = logging.getLogger(__name__)


@dataclass
class VectorStoreBuilder:
    """Constructs and persists a FAISS vector index along with metadata.

    Parameters
    ----------
    base_path:
        Directory where the vector store directory should be created.  A
        subdirectory will be created within this path whose name is
        derived from ``store_name``.  If a directory with the same
        name already exists a random suffix is appended to avoid
        collision.
    store_name:
        Desired name of the vector store.  The name should not
        contain directory separators.  On collisions the name is
        altered automatically.
    """

    base_path: str
    store_name: str

    def build(self, documents: List[Document], embeddings: List[List[float]]) -> str:
        """Build and persist a FAISS index from embeddings and metadata.

        Parameters
        ----------
        documents:
            List of :class:`~embedding_app.document.Document` objects.  The
            order of this list must correspond exactly to the order of
            the ``embeddings`` list.
        embeddings:
            List of embedding vectors returned from the embedding
            service.  Each embedding must be a sequence of floats of
            identical length.

        Returns
        -------
        str
            The final name of the created vector store directory.  This
            may differ from the requested ``store_name`` if a name
            collision occurred.  The directory will contain a FAISS
            index file named ``index.faiss`` and a ``metadata.json``
            file with the document metadata.

        Notes
        -----
        The function creates a single index using the exact L2 metric
        (:class:`faiss.IndexFlatL2`).  More advanced index types (e.g.
        HNSW, PQ) can be substituted here without changing the caller.
        """
        if len(documents) != len(embeddings):
            raise ValueError(
                f"Number of documents ({len(documents)}) does not match number of embeddings ({len(embeddings)})"
            )

        # Determine dimension from first embedding
        if not embeddings:
            raise ValueError("Cannot build vector store with no embeddings")
        dim = len(embeddings[0])

        # Convert embeddings to numpy array of type float32
        vectors = np.array(embeddings, dtype="float32")
        logger.debug("Building FAISS index with dimension %d for %d vectors", dim, len(vectors))

        # Create index with ID mapping so we can associate vectors with document ids
        index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        ids = np.arange(len(vectors), dtype="int64")
        index.add_with_ids(vectors, ids)

        # Prepare metadata mapping
        metadata_list: List[Dict[str, Any]] = []
        for doc_id, doc in enumerate(documents):
            entry: Dict[str, Any] = dict(doc.metadata)
            entry["text"] = doc.text
            entry["id"] = doc_id
            metadata_list.append(entry)

        # Create unique directory for the vector store
        final_name = ensure_unique_path(self.base_path, self.store_name)
        store_dir = Path(self.base_path) / final_name
        store_dir.mkdir(parents=True, exist_ok=True)

        # Persist index and metadata
        index_file = store_dir / "index.faiss"
        metadata_file = store_dir / "metadata.json"
        logger.info("Persisting FAISS index to %s", index_file)
        faiss.write_index(index, str(index_file))
        logger.info("Persisting metadata to %s", metadata_file)
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump(metadata_list, f, ensure_ascii=False, indent=2)

        return final_name