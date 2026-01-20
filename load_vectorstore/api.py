"""API entry point for serving vector store retrieval results.

Run this module to expose a lightweight HTTP endpoint that embeds
incoming queries, searches the FAISS index and returns scored
matches along with a concatenated context string suitable for RAG
prompts.  The application loads the vector store once at startup and
uses detailed logging to aid debugging and observability.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
import uvicorn

from ..config import EmbeddingConfig
from ..utils import setup_logging
from .loader import CachedVectorStoreManager, DEFAULT_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier used for caching the loaded store.")
    query: str = Field(..., description="User question or statement to embed and search.")
    top_k: int = Field(5, gt=0, description="Number of nearest neighbours to retrieve.")

    @validator("query")
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value

    @validator("session_id")
    def validate_session(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("session_id must not be empty")
        return value


class QueryResponse(BaseModel):
    results: list[Dict[str, Any]]
    context: str


def create_app(
    store_dir: str,
    embedding_config: EmbeddingConfig,
    log_dir: Optional[str] = None,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> FastAPI:
    """Create and return a FastAPI app bound to a vector store."""
    if log_dir:
        setup_logging(log_dir, logging.INFO)

    manager = CachedVectorStoreManager(
        store_dir,
        embedding_config=embedding_config,
        log_dir=log_dir,
        ttl_seconds=cache_ttl_seconds,
    )

    app = FastAPI(title="Vector Store Loader", version="0.1.0")
    app.state.manager = manager

    @app.get("/health")
    async def health() -> Dict[str, str]:
        logger.debug("Health check requested")
        return {"status": "ok"}

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest) -> QueryResponse:
        logger.info("Received query request for session %s with top_k=%d", request.session_id, request.top_k)
        try:
            payload = app.state.manager.query(request.session_id, request.query, top_k=request.top_k)
        except ValueError as exc:
            logger.warning("Validation error during query: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - runtime logging
            logger.exception("Failed to process query")
            raise HTTPException(status_code=500, detail="Query processing failed") from exc

        logger.info("Returning %d result(s) for query", len(payload["results"]))
        return QueryResponse(results=payload["results"], context=payload["context"])

    return app


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a vector store as a retrieval API.")
    parser.add_argument("--store_dir", required=True, help="Path to the persisted vector store directory.")
    parser.add_argument(
        "--embedding_endpoint",
        default="http://localhost:8001/v1/embeddings",
        help="URL of the embedding service used for query encoding.",
    )
    parser.add_argument(
        "--embedding_batch_size",
        type=int,
        default=4,
        help="Batch size used when calling the embedding endpoint.",
    )
    parser.add_argument(
        "--embedding_model_kwargs",
        help="Optional JSON string of extra model kwargs passed to the embedding endpoint.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind the HTTP server.")
    parser.add_argument("--port", type=int, default=8003, help="Port for the HTTP server.")
    parser.add_argument(
        "--log_dir",
        help="Optional log directory. Defaults to the vector store directory when not set.",
    )
    parser.add_argument(
        "--cache_ttl_seconds",
        type=int,
        default=DEFAULT_CACHE_TTL_SECONDS,
        help="Inactivity TTL (seconds) before a session-scoped loader is evicted.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    log_dir = args.log_dir or args.store_dir

    model_kwargs: Dict[str, Any] = {}
    if args.embedding_model_kwargs:
        try:
            model_kwargs = json.loads(args.embedding_model_kwargs)
        except Exception as exc:
            raise SystemExit(f"Failed to parse --embedding_model_kwargs: {exc}")

    embed_cfg = EmbeddingConfig(
        endpoint=args.embedding_endpoint,
        batch_size=args.embedding_batch_size,
        model_kwargs=model_kwargs,
    )

    app = create_app(args.store_dir, embed_cfg, log_dir=log_dir, cache_ttl_seconds=args.cache_ttl_seconds)

    logger.info("Starting Vector Store Loader API on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
