"""High level orchestration for chat with streaming, memory, and context."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .config import ChatConfig
from .llm_client import ChatLLMClient

try:  # Optional dependency for retrieval
    from load_vectorstore.loader import CachedVectorStoreManager  # type: ignore
except Exception as exc:  # pragma: no cover - optional import
    CachedVectorStoreManager = None
    _VSTORE_IMPORT_ERROR = exc

logger = logging.getLogger(__name__)


@dataclass
class ChatSessionState:
    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""
    intents: List[str] = field(default_factory=list)
    last_context: str = ""
    last_retrievals: List[Dict[str, object]] = field(default_factory=list)
    vector_store_dir: Optional[str] = None
    updated_at: float = field(default_factory=time.time)


class VectorStoreContextProvider:
    """Lazily instantiates loaders per store directory."""

    def __init__(self) -> None:
        self._managers: Dict[str, "CachedVectorStoreManager"] = {}

    def build_context(self, store_dir: str, session_id: str, query: str, top_k: int) -> Tuple[str, List[Dict[str, object]]]:
        if CachedVectorStoreManager is None:
            raise RuntimeError(f"Vector store support unavailable: {_VSTORE_IMPORT_ERROR}")  # type: ignore[name-defined]
        if not store_dir:
            raise ValueError("store_dir must be provided when requesting context")

        manager = self._managers.get(store_dir)
        if not manager:
            manager = CachedVectorStoreManager(store_dir)  # type: ignore[operator]
            self._managers[store_dir] = manager
        payload = manager.query(session_id, query, top_k=top_k)
        return payload.get("context", ""), payload.get("results", [])


class ChatService:
    """Core chat engine used by both the API and direct Python consumers."""

    def __init__(
        self,
        config: Optional[ChatConfig] = None,
        *,
        vector_store_provider: Optional[VectorStoreContextProvider] = None,
    ) -> None:
        self.config = config or ChatConfig()
        self.client = ChatLLMClient(self.config.llm)
        self.sessions: Dict[str, ChatSessionState] = {}
        self.vector_store_provider = vector_store_provider

    def stream_chat(
        self,
        session_id: str,
        message: str,
        *,
        vector_store_dir: Optional[str] = None,
        top_k: Optional[int] = None,
        enable_context: Optional[bool] = None,
        enable_summarisation: Optional[bool] = None,
        enable_intent_tracking: Optional[bool] = None,
        system_prompt: Optional[str] = None,
    ) -> Iterable[str]:
        """Stream the assistant reply while updating memory and summaries."""
        if not session_id:
            raise ValueError("session_id is required")
        if not message or not message.strip():
            raise ValueError("message is required")

        session = self.sessions.get(session_id) or self._create_session(session_id)
        session.vector_store_dir = session.vector_store_dir or vector_store_dir

        context_text = ""
        retrievals: List[Dict[str, object]] = []
        use_context = self._flag(enable_context, self.config.enable_context)
        if use_context and vector_store_dir and self.vector_store_provider:
            try:
                context_text, retrievals = self.vector_store_provider.build_context(
                    vector_store_dir,
                    session_id,
                    message,
                    top_k=top_k or self.config.context_top_k,
                )
            except Exception:
                logger.exception("Failed to fetch context for session %s", session_id)

        self._append_message(session, {"role": "user", "content": message})
        prompt_messages = self._build_prompt(
            session,
            context=context_text,
            system_prompt_override=system_prompt,
        )
        prompt_messages, truncated = self._enforce_prompt_budget(session, prompt_messages, self.config.max_prompt_tokens)

        def generator() -> Iterable[str]:
            assistant_reply = ""
            if truncated:
                notice = "Note: Some earlier conversation was truncated to fit the context window. "
                assistant_reply += notice
                yield notice
            for token in self.client.stream_completion(prompt_messages, model_kwargs=self.config.model_kwargs):
                assistant_reply += token
                yield token

            self._append_message(session, {"role": "assistant", "content": assistant_reply})
            session.last_context = context_text
            session.last_retrievals = retrievals
            session.updated_at = time.time()

            if self._flag(enable_summarisation, self.config.enable_summarisation):
                self._refresh_summary(session)

            if self._flag(enable_intent_tracking, self.config.enable_intent_tracking):
                self._track_intent(session, latest_user_message=message)

        return generator()

    def get_history(self, session_id: str) -> Dict[str, object]:
        """Return the recorded conversation, summary, and metadata."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"No chat session found for id '{session_id}'")
        return {
            "session_id": session.session_id,
            "messages": session.messages,
            "summary": session.summary,
            "intents": session.intents,
            "last_context": session.last_context,
            "last_retrievals": session.last_retrievals,
            "vector_store_dir": session.vector_store_dir,
            "updated_at": session.updated_at,
        }

    def list_sessions(self) -> List[Dict[str, object]]:
        """Return lightweight session metadata for UI selection."""
        payload = []
        for session in self.sessions.values():
            last_message = session.messages[-1]["content"] if session.messages else ""
            payload.append(
                {
                    "session_id": session.session_id,
                    "updated_at": session.updated_at,
                    "summary": session.summary,
                    "last_message": last_message,
                    "vector_store_dir": session.vector_store_dir,
                    "message_count": len(session.messages),
                    "intents": session.intents[-3:],
                }
            )
        return sorted(payload, key=lambda item: item.get("updated_at", 0), reverse=True)

    def _create_session(self, session_id: str) -> ChatSessionState:
        session = ChatSessionState(session_id=session_id)
        self.sessions[session_id] = session
        return session

    def _append_message(self, session: ChatSessionState, message: Dict[str, str]) -> None:
        session.messages.append(message)
        if len(session.messages) > self.config.max_history_messages:
            session.messages = session.messages[-self.config.max_history_messages :]

    def _build_prompt(
        self,
        session: ChatSessionState,
        *,
        context: str,
        system_prompt_override: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        system_prompt = system_prompt_override or self.config.system_prompt
        prompt: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if session.summary:
            prompt.append({"role": "system", "content": f"Conversation summary: {session.summary}"})
        if context:
            prompt.append({"role": "system", "content": f"Context for this turn:\n{context}"})
        prompt.extend(session.messages)
        return prompt

    def _refresh_summary(self, session: ChatSessionState) -> None:
        summary_messages = [
            {"role": "system", "content": self.config.summarise_prompt},
            {"role": "user", "content": self._messages_as_text(session.messages)},
        ]
        try:
            session.summary = self.client.complete(summary_messages, model_kwargs=self.config.model_kwargs)
            logger.debug("Updated summary for session %s", session.session_id)
        except Exception:
            logger.exception("Failed to update summary for session %s", session.session_id)

    def _track_intent(self, session: ChatSessionState, *, latest_user_message: str) -> None:
        intent_messages = [
            {"role": "system", "content": self.config.intent_prompt},
            {"role": "user", "content": latest_user_message},
        ]
        try:
            intent = self.client.complete(intent_messages, model_kwargs=self.config.model_kwargs)
            if intent:
                session.intents.append(intent.strip())
        except Exception:
            logger.exception("Failed to capture intent for session %s", session.session_id)

    @staticmethod
    def _messages_as_text(messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

    @staticmethod
    def _flag(overridden: Optional[bool], default: bool) -> bool:
        return default if overridden is None else overridden

    def _enforce_prompt_budget(
        self, session: ChatSessionState, prompt: List[Dict[str, str]], max_tokens: int
    ) -> tuple[List[Dict[str, str]], bool]:
        """If prompt exceeds the budget, collapse history into summary."""
        if max_tokens <= 0:
            return prompt, False

        token_count = sum(self._estimate_tokens(msg.get("content", "")) for msg in prompt)
        if token_count <= max_tokens:
            return prompt, False

        # Ensure we have a fresh summary to substitute for history.
        self._ensure_summary(session)

        system_msgs = [m for m in prompt if m.get("role") == "system"]
        user_msgs = [m for m in prompt if m.get("role") != "system"]
        latest_user = user_msgs[-1:]  # keep the current turn

        rebuilt: List[Dict[str, str]] = []
        rebuilt.extend(system_msgs)
        if session.summary:
            rebuilt.append({"role": "system", "content": f"Conversation summary: {session.summary}"})
        rebuilt.append(
            {
                "role": "system",
                "content": "History was replaced with a summary to fit the context window.",
            }
        )
        rebuilt.extend(latest_user)
        return rebuilt, True

    def _ensure_summary(self, session: ChatSessionState) -> None:
        if session.summary:
            return
        try:
            self._refresh_summary(session)
        except Exception:
            logger.exception("Failed to refresh summary while enforcing prompt budget for session %s", session.session_id)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Very rough token estimation (4 chars ≈ 1 token)."""
        return max(1, len(text) // 4)
