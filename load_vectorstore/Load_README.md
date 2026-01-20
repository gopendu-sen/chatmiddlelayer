# Vector Store Loader

This module loads a persisted FAISS vector store and exposes it for retrieval‑augmented chat. It pairs with the existing vector store builder and can be used either as a Python helper or as a small HTTP API.

## Python usage
- Configure logging once (recommended): `from embedding_app.utils import setup_logging; setup_logging("/tmp/logs")`
- Create the loader: `from embedding_app.load_vectorstore import load_vector_store, CachedVectorStoreManager`
- Load the store and query (single use):
  ```python
  from embedding_app.config import EmbeddingConfig

  loader = load_vector_store(
      "/path/to/vector/store",
      embedding_config=EmbeddingConfig(endpoint="http://localhost:8001/v1/embeddings"),
  )
  results = loader.search("How do I deploy this?", top_k=4)
  context = loader.build_context("How do I deploy this?", top_k=4)
  ```
- Each result includes the vector id, FAISS score, original text, and metadata.
- Session caching (per-session loader cached for 60 minutes of inactivity):
  ```python
  manager = CachedVectorStoreManager("/path/to/vector/store")
  payload = manager.query(session_id="abc123", query="How do I deploy this?", top_k=4)
  # payload contains {"results": [...], "context": "..."}
  ```

## API usage
- Run the API server (requires `fastapi` and `uvicorn`, now in `requirements.txt`):
  ```bash
  python -m embedding_app.load_vectorstore.api \
    --store_dir /path/to/vector/store \
    --embedding_endpoint http://localhost:8001/v1/embeddings \
    --port 8003
  ```
- Endpoints:
  - `GET /health` – quick readiness check.
  - `POST /query` – body: `{"session_id": "...", "query": "...", "top_k": 5}`. Response includes `results` and `context`.

## Logging
- Pass `--log_dir` (or rely on the store directory) when running the API to capture logs in `application.log`.
- The loader logs key lifecycle events: index/metadata loading, embedding latency, FAISS search timings, and query validation errors.
