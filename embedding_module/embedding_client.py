"""Client for interacting with a local embedding model API.

This module defines a simple wrapper around an HTTP endpoint that
accepts a list of strings and returns a list of dense embeddings.
Embedding models convert unstructured text into numerical vectors
that capture semantic meaning, enabling applications such as
similarity search【589231301807203†L8-L20】.  The client batches
requests to respect API limits and logs detailed information about
each call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Any
import time

import requests

from .config import EmbeddingConfig


logger = logging.getLogger(__name__)


@dataclass
class EmbeddingClient:
    """Wraps an HTTP embedding service for generating vector representations.

    Parameters
    ----------
    config:
        An :class:`~embedding_app.config.EmbeddingConfig` instance
        containing the endpoint URL, batch size and any additional
        keyword arguments to be forwarded with each request.
    """

    config: EmbeddingConfig

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """Generate embeddings for a collection of documents.

        The method sends the input documents to the configured
        embedding endpoint in batches of ``config.batch_size``.  Each
        request includes any ``model_kwargs`` specified on the
        configuration.  Responses are expected to be JSON objects
        containing a ``data`` field with a list of embeddings in the
        same order as the inputs.  Any HTTP or JSON errors are
        propagated as exceptions.  Detailed log messages record when
        calls are made and how long they take.

        Parameters
        ----------
        documents:
            List of strings to be embedded.  The order of the inputs
            is preserved in the output.

        Returns
        -------
        list of list of float
            Embeddings corresponding to each document.
        """
        if not documents:
            return []

        embeddings: List[List[float]] = []
        batch_size = self.config.batch_size
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            payload: Dict[str, Any] = {"input": batch}
            payload.update(self.config.model_kwargs)
            logger.debug(
                "Sending embedding request to %s with %d documents",
                self.config.endpoint,
                len(batch),
            )
            start_time = time.perf_counter()
            try:
                response = requests.post(self.config.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
            except Exception:
                logger.exception("Failed to obtain embeddings from the API")
                raise
            elapsed = time.perf_counter() - start_time
            logger.debug(
                "Received embedding response for %d documents in %.2f seconds",
                len(batch),
                elapsed,
            )
            # The API is expected to return a dictionary with a 'data' key
            # containing embeddings.  Each entry in 'data' may itself be
            # a dictionary; we handle both lists and dicts with 'embedding'.
            batch_embeddings: List[List[float]] = []
            for item in data.get("data", []):
                if isinstance(item, dict) and "embedding" in item:
                    batch_embeddings.append(item["embedding"])
                elif isinstance(item, list):
                    batch_embeddings.append(item)
                else:
                    raise ValueError(
                        "Unexpected embedding format returned from the API"
                    )
            if len(batch_embeddings) != len(batch):
                raise ValueError(
                    f"Expected {len(batch)} embeddings, got {len(batch_embeddings)}"
                )
            embeddings.extend(batch_embeddings)
        return embeddings