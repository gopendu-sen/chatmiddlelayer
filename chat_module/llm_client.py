"""Client wrapper for streaming chat-completions requests."""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, List, Optional

import requests

from .config import ChatLLMConfig

logger = logging.getLogger(__name__)


class ChatLLMClient:
    """Thin wrapper around a chat-completions endpoint with streaming support."""

    def __init__(self, config: ChatLLMConfig) -> None:
        self.config = config

    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        model_kwargs: Optional[Dict[str, object]] = None,
    ) -> Iterable[str]:
        """Yield tokens from the model as they arrive."""
        payload: Dict[str, object] = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
        }
        if model_kwargs:
            payload.update(model_kwargs)

        logger.info("Streaming chat completion to %s using model %s", self.config.endpoint, self.config.model)
        response = requests.post(
            self.config.endpoint,
            json=payload,
            stream=True,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()

        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8").strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON stream line: %s", line)
                continue

            token = self._extract_delta(payload)
            if token:
                yield token

    def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        model_kwargs: Optional[Dict[str, object]] = None,
    ) -> str:
        """Return a full completion (no streaming)."""
        payload: Dict[str, object] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        }
        if model_kwargs:
            payload.update(model_kwargs)

        logger.debug("Requesting non-streaming completion for %d message(s)", len(messages))
        response = requests.post(
            self.config.endpoint,
            json=payload,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return message.get("content", "") or ""

    @staticmethod
    def _extract_delta(payload: Dict[str, object]) -> str:
        try:
            choices = payload.get("choices") or []
            if not choices:
                return ""
            delta = choices[0].get("delta") or {}
            content = delta.get("content") or ""
            return str(content)
        except Exception:
            logger.debug("Failed to parse stream payload: %s", payload, exc_info=True)
            return ""
