export default function Guide() {
  return (
    <div className="grid" style={{ gap: 16 }}>
      <section className="card">
        <div className="headline">How to use this console</div>
        <p className="subhead">
          Three pages cover the RAG build pipeline, chat with context, and quick operational notes. Everything is wired to
          the middle-layer FastAPI server.
        </p>
        <div className="grid two" style={{ marginTop: 12 }}>
          <div className="card">
            <div className="section-title">1) Build a vector store</div>
            <ul>
              <li>Pick the source type: upload files, point at a folder, Git repo, or Confluence space.</li>
              <li>Set the base path (default <code>./stores</code>) and a memorable store name.</li>
              <li>Always provide a session id for traceability; it flows into embedding metadata and logs.</li>
              <li>Click “Build vector store” to hit <code>/vector-store/build</code> or the upload variant.</li>
            </ul>
          </div>
          <div className="card">
            <div className="section-title">2) Chat with retrieval</div>
            <ul>
              <li>Confirm the session id (or create a fresh one) in the header pill.</li>
              <li>Optionally paste a vector store path; toggle context, summaries, and intents.</li>
              <li>Send a message to stream from <code>/chat</code>. History is kept server-side.</li>
              <li>Re-open past sessions via the “Past conversations” panel; history comes from <code>/chat/history</code>.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">Endpoints wired here</div>
        <div className="grid two" style={{ gap: 12 }}>
          <div>
            <h4>Vector stores</h4>
            <ul>
              <li>
                <code>POST /vector-store/build</code> – JSON for folder/git/confluence sources. Session id is optional but
                recommended.
              </li>
              <li>
                <code>POST /vector-store/build/upload</code> – multipart upload from the UI; files are staged under
                <code>_uploads</code>.
              </li>
              <li>
                <code>POST /vector-store/query</code> – used during chat when context is enabled.
              </li>
            </ul>
          </div>
          <div>
            <h4>Chat</h4>
            <ul>
              <li>
                <code>POST /chat</code> – streams only the latest assistant reply; server keeps memory, summaries, intents.
              </li>
              <li>
                <code>GET /chat/history/{"{session_id}"}</code> – retrieves messages, summary, last context and retrievals.
              </li>
              <li>
                <code>GET /chat/sessions</code> – lists server-known sessions for quick selection in the UI.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">TD-flavoured design decisions</div>
        <ul>
          <li>High-contrast deep greens with warm amber accents for clarity and accessibility.</li>
          <li>Space Grotesk type for a contemporary, financial-grade feel; generous padding and rounded corners.</li>
          <li>Cards and pills clearly call out session identity and status so audits are easy.</li>
        </ul>
      </section>
    </div>
  );
}
