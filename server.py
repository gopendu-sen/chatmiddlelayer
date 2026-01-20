"""Unified FastAPI server exposing embedding build, retrieval, and chat."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
import uvicorn

from embedding_module.cli import run_pipeline
from embedding_module.config import AppConfig, ConfluenceSettings, EmbeddingConfig, GitSettings
from embedding_module.utils import setup_logging
from load_vectorstore.loader import CachedVectorStoreManager
from chat_module import ChatConfig, ChatLLMConfig
from chat_module.service import ChatService, VectorStoreContextProvider

logger = logging.getLogger(__name__)


# ---------- Request Models ----------
class GitSettingsRequest(BaseModel):
    url: str
    exclude_extensions: Optional[list[str]] = None
    include_extensions: Optional[list[str]] = None
    max_files: Optional[int] = None
    branch: Optional[str] = None


class ConfluenceSettingsRequest(BaseModel):
    url: str
    user: str
    token: str
    space_key: str
    max_pages: Optional[int] = None


class EmbeddingConfigRequest(BaseModel):
    endpoint: str = "http://localhost:8001/v1/embeddings"
    batch_size: int = 32
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)


class BuildVectorStoreRequest(BaseModel):
    vector_store_path: str
    vector_store_name: str
    session_id: Optional[str] = Field(None, description="Recorded in metadata for audit tracing.")
    files_location: Optional[str] = None
    git_settings: Optional[GitSettingsRequest] = None
    confluence_settings: Optional[ConfluenceSettingsRequest] = None
    embedding_config: EmbeddingConfigRequest = Field(default_factory=EmbeddingConfigRequest)

    @validator("vector_store_path", "vector_store_name")
    def _not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be empty")
        return value


class RetrievalRequest(BaseModel):
    store_dir: str
    session_id: str
    query: str
    top_k: int = Field(4, gt=0)

    @validator("store_dir", "session_id", "query")
    def _not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be empty")
        return value


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique chat session identifier.")
    message: str = Field(..., description="User message to send to the model.")
    vector_store_dir: Optional[str] = Field(
        None, description="Optional path to a persisted vector store for retrieval."
    )
    top_k: int = Field(4, gt=0, description="Number of context chunks to retrieve when enabled.")
    enable_context: bool = True
    enable_summarisation: bool = True
    enable_intent_tracking: bool = True
    system_prompt: Optional[str] = Field(
        None, description="Optional system prompt override for this request."
    )

    @validator("session_id", "message")
    def _not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be empty")
        return value


class HistoryResponse(BaseModel):
    session_id: str
    summary: str = ""
    intents: list[str] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    last_context: str = ""
    last_retrievals: list[dict] = Field(default_factory=list)
    vector_store_dir: Optional[str] = None
    updated_at: float


# ---------- Helpers ----------
class VectorStoreRouter:
    """Manages CachedVectorStoreManager instances keyed by store directory."""

    def __init__(self) -> None:
        self._managers: Dict[str, CachedVectorStoreManager] = {}

    def _get_manager(self, store_dir: str) -> CachedVectorStoreManager:
        manager = self._managers.get(store_dir)
        if not manager:
            manager = CachedVectorStoreManager(store_dir)
            self._managers[store_dir] = manager
        return manager

    def query(self, store_dir: str, session_id: str, query: str, top_k: int) -> Dict[str, Any]:
        manager = self._get_manager(store_dir)
        return manager.query(session_id, query, top_k=top_k)


# ---------- FastAPI Factory ----------
def create_app(log_dir: str = "./logs", chat_config: Optional[ChatConfig] = None) -> FastAPI:
    setup_logging(log_dir, logging.INFO)

    vector_router = VectorStoreRouter()
    vector_provider = VectorStoreContextProvider()
    chat_service = ChatService(chat_config, vector_store_provider=vector_provider)

    app = FastAPI(title="Middle Layer Server", version="0.1.0")
    app.state.vector_router = vector_router
    app.state.vector_provider = vector_provider
    app.state.chat_service = chat_service

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/vector-store/build")
    async def build_vector_store(request: BuildVectorStoreRequest) -> Dict[str, str]:
        logger.info(
            "Received build request for store %s (session_id=%s)",
            request.vector_store_name,
            request.session_id,
        )
        try:
            config = _to_app_config(request)
            store_name = await run_in_threadpool(run_pipeline, config)
        except Exception as exc:
            logger.exception("Vector store build failed (session_id=%s)", request.session_id)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        full_path = os.path.join(request.vector_store_path, store_name)
        logger.info(
            "Vector store build complete: %s (session_id=%s)",
            full_path,
            request.session_id,
        )
        return {"store_name": store_name, "path": full_path}

    @app.post("/vector-store/query")
    async def query_vector_store(request: RetrievalRequest) -> Dict[str, Any]:
        logger.info(
            "Querying vector store %s for session %s",
            request.store_dir,
            request.session_id,
        )
        try:
            payload = await run_in_threadpool(
                app.state.vector_router.query,
                request.store_dir,
                request.session_id,
                request.query,
                request.top_k,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Vector store query failed (session_id=%s)", request.session_id)
            raise HTTPException(status_code=500, detail="Vector store query failed") from exc

        return payload

    @app.post("/chat")
    async def chat(request: ChatRequest):
        logger.info(
            "Streaming chat for session %s (context=%s)",
            request.session_id,
            "on" if request.enable_context else "off",
        )
        try:
            stream = app.state.chat_service.stream_chat(
                request.session_id,
                request.message,
                vector_store_dir=request.vector_store_dir,
                top_k=request.top_k,
                enable_context=request.enable_context,
                enable_summarisation=request.enable_summarisation,
                enable_intent_tracking=request.enable_intent_tracking,
                system_prompt=request.system_prompt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Chat request failed (session_id=%s)", request.session_id)
            raise HTTPException(status_code=500, detail="Chat request failed") from exc

        return StreamingResponse(stream, media_type="text/plain")

    @app.get("/chat/history/{session_id}", response_model=HistoryResponse)
    async def chat_history(session_id: str):
        logger.info("Fetching history for session %s", session_id)
        try:
            payload = app.state.chat_service.get_history(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return payload

    return app


# ---------- CLI ----------
def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the middle-layer server for RAG chat.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8010, help="Port to bind.")
    parser.add_argument("--log_dir", default="./logs", help="Directory for application logs.")
    parser.add_argument("--llm_endpoint", default="http://localhost:8000/v1/chat/completions", help="LLM endpoint.")
    parser.add_argument("--llm_model", default="qwen2.5-instruct", help="Model name for completions.")
    parser.add_argument("--request_timeout", type=int, default=60, help="Timeout for LLM calls (seconds).")
    parser.add_argument("--context_top_k", type=int, default=4, help="Chunks to retrieve from the vector store.")
    parser.add_argument("--max_history_messages", type=int, default=20, help="Max messages kept in rolling memory.")
    parser.add_argument("--disable_context", action="store_true", help="Disable vector store context injection.")
    parser.add_argument("--disable_summarisation", action="store_true", help="Disable background summarisation.")
    parser.add_argument("--disable_intents", action="store_true", help="Disable intent tracking.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    chat_cfg = ChatConfig(
        llm=ChatLLMConfig(
            endpoint=args.llm_endpoint,
            model=args.llm_model,
            request_timeout=args.request_timeout,
        ),
        enable_context=not args.disable_context,
        enable_summarisation=not args.disable_summarisation,
        enable_intent_tracking=not args.disable_intents,
        context_top_k=args.context_top_k,
        max_history_messages=args.max_history_messages,
    )

    app = create_app(args.log_dir, chat_cfg)
    logger.info("Starting middle-layer server on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


# ---------- Utilities ----------
def _to_app_config(request: BuildVectorStoreRequest) -> AppConfig:
    git_cfg = GitSettings(**request.git_settings.dict()) if request.git_settings else None
    conf_cfg = ConfluenceSettings(**request.confluence_settings.dict()) if request.confluence_settings else None
    embed_cfg = EmbeddingConfig(**request.embedding_config.dict())
    return AppConfig(
        vector_store_path=request.vector_store_path,
        vector_store_name=request.vector_store_name,
        session_id=request.session_id,
        files_location=request.files_location,
        git_settings=git_cfg,
        confluence_settings=conf_cfg,
        embedding_config=embed_cfg,
    )


if __name__ == "__main__":
    main()
