# Chat Module

This module streams chat responses from a local Qwen 2.5 instruct model while
automatically layering in retrieval context, conversation memory, summaries and
intent tracking. It can be embedded directly in Python code or exposed as a
FastAPI service.

## Features
- Streams responses from `http://localhost:8000/v1/chat/completions` (OpenAI-style).
- Optional vector store context (FAISS) pulled per session when a store path is provided.
- Rolling memory with automatic summarisation and per-turn intent detection (all on by default).
- History retrieval endpoint returns the full chat log, latest context and intents.

## Python usage
```python
from chat_module import ChatConfig, ChatService
from chat_module.service import VectorStoreContextProvider

service = ChatService(
    ChatConfig(),
    vector_store_provider=VectorStoreContextProvider(),  # optional if you want retrieval
)

stream = service.stream_chat(
    session_id="abc123",
    message="How do I deploy this service?",
    vector_store_dir="/path/to/vector/store",  # omit to skip retrieval
)

full_reply = "".join(stream)  # iterate to stream tokens; this collects everything
history = service.get_history("abc123")
```

## API usage
Run the service:
```bash
python -m chat_module.api --host 0.0.0.0 --port 8005 \
  --llm_endpoint http://localhost:8000/v1/chat/completions \
  --llm_model qwen2.5-instruct
```

Key endpoints:
- `GET /health` – readiness probe.
- `POST /chat` – body:
  ```json
  {
    "session_id": "abc123",
    "message": "What's new?",
    "vector_store_dir": "/path/to/vector/store",
    "top_k": 4,
    "system_prompt": "You are a release notes assistant.",
    "enable_context": true,
    "enable_summarisation": true,
    "enable_intent_tracking": true
  }
  ```
  Streams the latest assistant reply only; history/context are kept server side.
- `GET /history/{session_id}` – returns messages, running summary, intents, last context,
  retrieval metadata and stored vector store path (when provided earlier).

## Behaviour notes
- Context, summarisation and intent tracking are enabled by default and can be toggled per call.
- System prompt can be overridden per request; when omitted the default assistant prompt is used.
- Prompts are capped at a ~30k token budget (`max_prompt_tokens`). If exceeded, chat history is replaced with the running summary and the client is notified.
- Streaming replies never include prior exchanges; memory is kept server-side and summarised after each turn.
- The vector store provider is optional. If `load_vectorstore` dependencies are unavailable the chat
  still works without retrieval.
