# Chat GUI (TD Middle Layer Console)

Modern, TD-themed React/Vite frontend for the middle-layer FastAPI server. Three pages cover RAG build, chat, and guidance with session-aware flows.

## Features
- **RAG Builder:** upload files or point to folders/Git/Confluence to build vector stores via `/vector-store/build` or `/vector-store/build/upload`. Shows live status and latest store path so you can reuse it in chat.
- **Chat Ops:** stream from `/chat`, toggle retrieval (`vector_store_dir`, `top_k`), summaries, and intents; browse server-side sessions via `/chat/sessions`; pull history from `/chat/history/{session_id}`. Chat bubbles are streamed, with a scrollable transcript.
- **Guide:** in-app usage notes, endpoint references, and TD design notes.
- **Session-first UX:** Session ids live in the header pill. Changing it updates all forms and every request payload; building a store also records the session id in metadata.

## Quick start
```bash
cd chat_gui
npm install
npm run dev        # default API base http://localhost:8010
# or set a different API base
VITE_API_BASE=http://localhost:9000 npm run dev
```

## Build
```bash
npm run build
npm run preview
```

## Notes
- **API endpoints used:**
  - `POST /vector-store/build` (JSON) and `POST /vector-store/build/upload` (multipart) for RAG builds.
  - `POST /chat` for streaming replies; `GET /chat/history/{session_id}` for transcripts; `GET /chat/sessions` for server-known sessions.
  - `POST /vector-store/query` is invoked server-side when chat has `enable_context` and a `vector_store_dir`.
- **RAG builder sources:** Upload (files staged server-side under `<vector_store_path>/_uploads/`), local folder path, Git repo (URL + optional branch), Confluence (url/user/token/space).
- **State handling:** Session id and known vector store paths persist in `localStorage` (`td.session`, `td.vectorStores`) for quick reuse across page reloads.
- **Styling:** Space Grotesk font, TD green gradient background, amber accents, glassmorphism cards, and high-contrast text for accessibility.
- Fonts: Space Grotesk; TD greens with amber accents for accessibility.
- Streaming uses the Fetch streaming reader; if the browser blocks streams you’ll see an error in the assistant bubble.
