"""Command line interface for the vector store generator.

This module defines a `main` function which orchestrates the
end‑to‑end processing pipeline.  It parses command line arguments,
performs basic validation, configures logging and then invokes the
appropriate handlers to convert documents into embeddings and build
a FAISS vector index.  When run as a script the utility prints
the name of the created vector store directory upon successful
completion.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import List

from .config import AppConfig, GitSettings, ConfluenceSettings, EmbeddingConfig
from .utils import setup_logging
from .git_parser import GitRepositoryHandler
from .confluence_parser import ConfluenceSpaceHandler
from .factory import ParserFactory
from .embedding_client import EmbeddingClient
from .vector_store import VectorStoreBuilder
from .document import Document
from .utils import list_files


logger = logging.getLogger(__name__)


def parse_args(argv: List[str] | None = None) -> AppConfig:
    """Parse command line arguments into an AppConfig instance."""
    parser = argparse.ArgumentParser(
        description=(
            "Process documents from the filesystem, a Git repository or "
            "a Confluence space and build a FAISS vector store using a "
            "local embedding model."
        )
    )
    parser.add_argument("--vector_store_path", required=True, help="Directory where the vector store will be written")
    parser.add_argument("--vector_store_name", required=True, help="Name of the vector store to create")
    parser.add_argument("--session_id", help="Optional session identifier recorded in metadata")
    parser.add_argument(
        "--files_location", help="Path to a file or directory containing documents to process"
    )
    parser.add_argument(
        "--git_settings",
        type=str,
        help=(
            "JSON string with Git settings: {\"url\": ..., \"exclude_extensions\": [...], "
            "\"include_extensions\": [...], \"max_files\": 50, \"branch\": ...}"
        ),
    )
    parser.add_argument(
        "--confluence_settings",
        type=str,
        help=(
            "JSON string with Confluence settings: {\"url\": ..., \"user\": ..., \"token\": ..., "
            "\"space_key\": ..., \"max_pages\": 50}"
        ),
    )
    parser.add_argument(
        "--embedding_config",
        type=str,
        help=(
            "JSON string with embedding configuration: {\"endpoint\": ..., \"batch_size\": ..., "
            "\"model_kwargs\": {...}}"
        ),
    )
    parser.add_argument(
        "--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging verbosity"
    )
    args = parser.parse_args(argv)

    # Parse optional JSON settings
    git_cfg = None
    if args.git_settings:
        try:
            git_dict = json.loads(args.git_settings)
            git_cfg = GitSettings(**git_dict)
        except Exception as exc:
            raise SystemExit(f"Failed to parse --git_settings: {exc}")

    conf_cfg = None
    if args.confluence_settings:
        try:
            conf_dict = json.loads(args.confluence_settings)
            conf_cfg = ConfluenceSettings(**conf_dict)
        except Exception as exc:
            raise SystemExit(f"Failed to parse --confluence_settings: {exc}")

    embed_cfg = EmbeddingConfig()
    if args.embedding_config:
        try:
            embed_dict = json.loads(args.embedding_config)
            embed_cfg = EmbeddingConfig(**embed_dict)
        except Exception as exc:
            raise SystemExit(f"Failed to parse --embedding_config: {exc}")

    config = AppConfig(
        vector_store_path=args.vector_store_path,
        vector_store_name=args.vector_store_name,
        session_id=args.session_id,
        files_location=args.files_location,
        git_settings=git_cfg,
        confluence_settings=conf_cfg,
        embedding_config=embed_cfg,
    )

    # Setup logging at parse time to capture logs from argument errors
    setup_logging(config.vector_store_path, getattr(logging, args.log_level))
    return config


def collect_documents(config: AppConfig) -> List[Document]:
    """Collect documents from the specified sources.

    At least one of files_location, git_settings or confluence_settings
    must be provided.  Each source is processed in turn and the
    resulting documents concatenated.
    """
    documents: List[Document] = []
    factory = ParserFactory()
    # Process files from local file system
    if config.files_location:
        path = config.files_location
        if os.path.isfile(path):
            parser = factory.get_parser(path)
            if parser:
                documents.extend(parser.parse(path))
            else:
                logger.warning("Unsupported file type: %s", path)
        elif os.path.isdir(path):
            for file_path in list_files(path):
                parser = factory.get_parser(file_path)
                if parser:
                    documents.extend(parser.parse(file_path))
                else:
                    logger.debug("Skipping unsupported file: %s", file_path)
        else:
            logger.error("files_location %s does not exist", path)

    # Process Git repository
    if config.git_settings:
        handler = GitRepositoryHandler(config.git_settings)
        docs = handler.process()
        documents.extend(docs)

    # Process Confluence space
    if config.confluence_settings:
        handler = ConfluenceSpaceHandler(config.confluence_settings)
        docs = handler.process()
        documents.extend(docs)

    if not documents:
        raise RuntimeError(
            "No documents were collected. Please provide a valid files_location, git_settings or confluence_settings."
        )

    # Attach session id to each document's metadata if provided
    if config.session_id:
        for doc in documents:
            doc.metadata["session_id"] = config.session_id
    return documents


def run_pipeline(config: AppConfig) -> str:
    """Execute the full processing pipeline and return the store name."""
    documents = collect_documents(config)
    # Extract texts for embedding
    texts = [doc.text for doc in documents]
    embedding_client = EmbeddingClient(config.embedding_config)
    logger.info("Calling embedding service for %d documents", len(texts))
    embeddings = embedding_client.embed_documents(texts)
    # Build vector store
    builder = VectorStoreBuilder(config.vector_store_path, config.vector_store_name)
    store_name = builder.build(documents, embeddings)
    return store_name


def main(argv: List[str] | None = None) -> None:
    """Entry point for the command line interface."""
    config = parse_args(argv)
    try:
        store_name = run_pipeline(config)
        print(
            f"Vector store '{store_name}' created successfully at {os.path.join(config.vector_store_path, store_name)}"
        )
    except Exception as exc:
        logger.exception("An error occurred: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()