"""Chat orchestration module for streaming conversations with memory and context.

This package wires a chat-completions capable LLM (defaulting to a local Qwen
2.5 endpoint) with optional vector-store retrieval, conversational memory,
summarisation, and intent tracking. The primary entry points are
``chat_module.api.create_app`` for running the HTTP service and
``chat_module.service.ChatService`` for embedding the chat engine directly
into Python code.
"""

from .config import ChatConfig, ChatLLMConfig
from .service import ChatService

__all__ = ["ChatConfig", "ChatLLMConfig", "ChatService"]
