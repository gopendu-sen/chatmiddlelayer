"""FastAPI entry point for the chat module."""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
import uvicorn

from embedding_module.utils import setup_logging
from .config import ChatConfig, ChatLLMConfig
from .service import ChatService, VectorStoreContextProvider

logger = logging.getLogger(__name__)


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


def create_app(chat_config: Optional[ChatConfig] = None, *, log_dir: Optional[str] = None) -> FastAPI:
    if log_dir:
        setup_logging(log_dir, logging.INFO)

    provider = VectorStoreContextProvider()
    service = ChatService(chat_config, vector_store_provider=provider)

    app = FastAPI(title="Chat Module", version="0.1.0")
    app.state.service = service

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(request: ChatRequest):
        try:
            stream = app.state.service.stream_chat(
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
            logger.exception("Chat request failed")
            raise HTTPException(status_code=500, detail="Chat request failed") from exc

        return StreamingResponse(stream, media_type="text/plain")

    @app.get("/history/{session_id}", response_model=HistoryResponse)
    async def history(session_id: str):
        try:
            payload = app.state.service.get_history(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return payload

    return app


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the chat service with streaming responses.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8004, help="Port to bind.")
    parser.add_argument("--log_dir", help="Directory for application logs.")
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

    app = create_app(chat_cfg, log_dir=args.log_dir)
    logger.info("Starting chat service on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
