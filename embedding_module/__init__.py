"""Top‑level package for the vector store generation utility.

This package exposes all of the public interfaces required to build a
retrieval‑augmented generation (RAG) vector store from a variety of
source documents.  The design follows a factory pattern to
dynamically select the appropriate document parser based on file
extension and provides utilities for cloning Git repositories,
retrieving pages from Confluence and converting unstructured text
into embeddings via a local embedding API.

The modules contained herein are organised as follows:

* :mod:`embedding_app.cli` – command line entry point and argument
  parsing.
* :mod:`embedding_app.config` – data classes describing the
  configuration objects passed around the system.
* :mod:`embedding_app.document` – simple data structures for
  representing documents and associated metadata.
* :mod:`embedding_app.pars ers` – concrete implementations of
  document parsers for different file formats. Each parser exposes
  a :class:`~embedding_app.parsers.base_parser.DocumentParser`
  interface.
* :mod:`embedding_app.factory` – a factory implementation that
  selects the appropriate parser based on file extension.
* :mod:`embedding_app.git_parser` and :mod:`embedding_app.confluence_parser` –
  utilities for retrieving documents from Git and Confluence.
* :mod:`embedding_app.embedding_client` – a thin wrapper around the
  embedding API endpoint.
* :mod:`embedding_app.vector_store` – logic to build a FAISS index
  from embeddings and persist it to disk.

The entry point for the command line application is the
:func:`embedding_app.cli.main` function. See the README for usage
examples.
"""

from .document import Document
from .config import AppConfig
from .embedding_client import EmbeddingClient
from .vector_store import VectorStoreBuilder
from .factory import ParserFactory
from .git_parser import GitRepositoryHandler
from .confluence_parser import ConfluenceSpaceHandler
from .parsers.base_parser import DocumentParser

__all__ = [
    "Document",
    "AppConfig",
    "EmbeddingClient",
    "VectorStoreBuilder",
    "ParserFactory",
    "GitRepositoryHandler",
    "ConfluenceSpaceHandler",
    "DocumentParser",
]