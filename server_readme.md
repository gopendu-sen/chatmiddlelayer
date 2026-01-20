# Middle Layer Server (Embedding + Retrieval + Chat)

This FastAPI service exposes a single endpoint surface for building vector
stores, querying retrieval context, and streaming chat responses through the
Qwen 2.5 model. It sits between your Chat UI and local model services, keeping
session-aware audit logs and reusing the existing embedding, vector-store load,
and chat modules.

## Architecture
- **Embedding build (`/vector-store/build`)**: runs the existing pipeline to
  parse sources (files/Git/Confluence), call the embedding endpoint, and persist
  a FAISS store. Optional `session_id` is written into document metadata and
  echoed in logs for traceability.
- **Retrieval (`/vector-store/query`)**: caches loaders per `store_dir` and
  returns `results` and concatenated `context` using `CachedVectorStoreManager`.
- **Chat (`/chat`)**: streams only the latest assistant reply. Injects optional
  vector-store context, rolling summaries, and intent tracking. Histories are
  retrievable via `/chat/history/{session_id}`.
- **Logging & audit**: `log_dir/application.log` captures all calls with
  `session_id` baked into log lines. Chat histories and vector-store metadata
  (when provided) also carry the session id.

## Installation
Use the existing dependencies:
```bash
pip install -r embedding_module/requirements.txt
```
Ensure your services are reachable:
- Embeddings: `http://localhost:8001/v1/embeddings` (default)
- Chat/LLM: `http://localhost:8000/v1/chat/completions` (default)

## Run the server
```bash
python server.py --host 0.0.0.0 --port 8010 \
  --llm_endpoint http://localhost:8000/v1/chat/completions \
  --llm_model qwen2.5-instruct \
  --log_dir ./logs
```

## Endpoints
- `GET /health` – readiness.
- `POST /vector-store/build` – build a store.
  ```json
  {
    "vector_store_path": "./stores",
    "vector_store_name": "kb_store",
    "session_id": "build-123",           // optional, logged + stored
    "files_location": "./docs",          // or git_settings / confluence_settings
    "embedding_config": {
      "endpoint": "http://localhost:8001/v1/embeddings",
      "batch_size": 32,
      "model_kwargs": {}
    }
  }
  ```
  Response: `{"store_name": "kb_store", "path": "./stores/kb_store"}`.
- `POST /vector-store/query`
  ```json
  {
    "store_dir": "./stores/kb_store",
    "session_id": "chat-abc",
    "query": "How to deploy?",
    "top_k": 4
  }
  ```
  Response: `{"results": [...], "context": "..."}`.
- `POST /chat` – streams only the latest reply (text/plain chunked).
  ```json
  {
    "session_id": "chat-abc",
    "message": "How do I deploy?",
    "vector_store_dir": "./stores/kb_store",
    "top_k": 4,
    "system_prompt": "You are a deployment assistant.",
    "enable_context": true,
    "enable_summarisation": true,
    "enable_intent_tracking": true
  }
  ```
- `GET /chat/history/{session_id}` – returns messages, summary, intents,
  latest context, retrieval metadata, and last update time.

## Usage examples
- Build a store:
  ```bash
  curl -X POST http://localhost:8010/vector-store/build \
    -H "Content-Type: application/json" \
    -d '{"vector_store_path":"./stores","vector_store_name":"kb_store","files_location":"./docs"}'
  ```
- Query a store:
  ```bash
  curl -X POST http://localhost:8010/vector-store/query \
    -H "Content-Type: application/json" \
    -d '{"store_dir":"./stores/kb_store","session_id":"chat-1","query":"reset password","top_k":3}'
  ```
- Stream chat (shows chunks):
  ```bash
  curl -N -X POST http://localhost:8010/chat \
    -H "Content-Type: application/json" \
    -d '{"session_id":"chat-1","message":"Explain the reset steps","vector_store_dir":"./stores/kb_store"}'
  ```
- Inspect history:
  ```bash
  curl http://localhost:8010/chat/history/chat-1
  ```

## Operational notes & best practices
- **Session IDs**: choose stable IDs per user/thread; they tie together chat
  memory, retrieval caches, build metadata, and logs for audits.
- **Threading**: build and retrieval run in a threadpool to keep the event loop
  responsive while using CPU-bound FAISS searches and I/O-bound embedding calls.
- **Retrieval**: keep `top_k` modest (3–8) for focused context. The server never
  returns previous chats to the client; only the latest stream.
- **Logging**: logs are written to `log_dir` (`./logs` by default). Include the
  session id in requests so the log line and stored metadata are traceable.
- **LLM safety**: default system prompt keeps responses concise and avoids
  leaking internal notes. Override per request via `system_prompt` when needed.
- **Scaling**: front with a reverse proxy for TLS and rate limiting; run UVicorn
  with multiple workers for throughput; persist chat histories externally if
  long-lived conversations are required.
