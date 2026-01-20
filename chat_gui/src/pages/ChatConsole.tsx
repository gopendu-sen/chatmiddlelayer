import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, fetchHistory, listSessions } from "../lib/api";
import { ChatMessage, HistoryResponse, SessionSummary } from "../lib/types";
import { generateSessionId } from "../utils/session";

interface Props {
  sessionId: string;
  knownStores: string[];
  onSessionChange: (id: string) => void;
  onStoreAdded: (path: string) => void;
}

const decoder = new TextDecoder();

export default function ChatConsole({ sessionId, knownStores, onSessionChange, onStoreAdded }: Props) {
  const [currentSession, setCurrentSession] = useState(sessionId);
  const [vectorStoreDir, setVectorStoreDir] = useState(knownStores[0] || "");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [sessionList, setSessionList] = useState<SessionSummary[]>([]);
  const [topK, setTopK] = useState(4);
  const [enableContext, setEnableContext] = useState(true);
  const [enableSummary, setEnableSummary] = useState(true);
  const [enableIntents, setEnableIntents] = useState(true);

  const chatScroller = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setCurrentSession(sessionId);
  }, [sessionId]);

  useEffect(() => {
    if (!currentSession) return;
    loadHistory(currentSession);
  }, [currentSession]);

  useEffect(() => {
    listSessions()
      .then(setSessionList)
      .catch(() => setSessionList([]));
  }, []);

  const loadHistory = async (id: string) => {
    try {
      const history = await fetchHistory(id);
      setMessages(history.messages || []);
      if (history.vector_store_dir) {
        setVectorStoreDir(history.vector_store_dir);
        onStoreAdded(history.vector_store_dir);
      }
      setStatus(`Loaded history for ${id}`);
    } catch {
      setMessages([]);
      setStatus("New conversation");
    }
  };

  const handleSend = async (evt?: FormEvent) => {
    evt?.preventDefault();
    if (!input.trim() || isSending) return;
    const userMessage = input.trim();
    const sessionToUse = currentSession || generateSessionId();
    onSessionChange(sessionToUse);
    setCurrentSession(sessionToUse);
    setInput("");
    setIsSending(true);
    setStatus("Streaming response…");

    setMessages((prev) => [...prev, { role: "user", content: userMessage }, { role: "assistant", content: "" }]);
    const assistantIndex = messages.length + 1;

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionToUse,
          message: userMessage,
          vector_store_dir: vectorStoreDir || null,
          top_k: topK,
          enable_context: enableContext,
          enable_summarisation: enableSummary,
          enable_intent_tracking: enableIntents,
        }),
      });

      if (!response.body) {
        throw new Error("Streaming is not supported by this browser.");
      }

      const reader = response.body.getReader();
      let assistantText = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value);
        updateAssistantMessage(assistantIndex, assistantText);
        chatScroller.current?.scrollTo({ top: chatScroller.current.scrollHeight, behavior: "smooth" });
      }
      updateAssistantMessage(assistantIndex, assistantText);
      setStatus("Done");
      refreshSessions();
    } catch (error: any) {
      updateAssistantMessage(assistantIndex, `Error: ${error?.message || error}`);
      setStatus("Failed to send");
    } finally {
      setIsSending(false);
    }
  };

  const refreshSessions = async () => {
    try {
      const sessions = await listSessions();
      setSessionList(sessions);
    } catch {
      /* ignore */
    }
  };

  const updateAssistantMessage = (index: number, content: string) => {
    setMessages((prev) => prev.map((msg, idx) => (idx === index ? { ...msg, content } : msg)));
  };

  const summary = useMemo(() => {
    if (messages.length === 0) return "No turns yet";
    return `${messages.length} messages · ${vectorStoreDir ? "Context on" : "Context off"}`;
  }, [messages.length, vectorStoreDir]);

  const currentSessions = useMemo(() => {
    if (!sessionList.length) return [];
    return sessionList.slice(0, 8);
  }, [sessionList]);

  return (
    <div className="grid" style={{ gap: 20 }}>
      <section className="hero">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="headline">Chat with memory + retrieval</div>
              <p className="subhead">
                TD-themed console that streams directly from the middle layer, with session-aware memory and optional
                vector-store grounding.
              </p>
            </div>
            <div className="badge" aria-live="polite">
              <span>Session</span>
              <strong>{currentSession}</strong>
            </div>
          </div>

          <form className="grid two" style={{ marginTop: 14 }} onSubmit={handleSend}>
            <div className="card">
              <div className="section-title">Conversation controls</div>
              <label className="label" htmlFor="session-id">
                Session id
              </label>
              <input
                id="session-id"
                className="input"
                value={currentSession}
                onChange={(e) => {
                  setCurrentSession(e.target.value);
                  onSessionChange(e.target.value);
                }}
                placeholder="td-session-123"
              />
              <div className="chip-row" style={{ marginTop: 10 }}>
                <button type="button" className="button secondary" onClick={() => handleSend()} disabled={!input.trim()}>
                  Send now
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => {
                    const next = generateSessionId();
                    setCurrentSession(next);
                    onSessionChange(next);
                    setMessages([]);
                    setStatus("New session started");
                  }}
                >
                  Fresh session
                </button>
              </div>
              <div className="status" style={{ marginTop: 10 }}>
                <strong>Status:</strong> {status}
              </div>
            </div>

            <div className="card">
              <div className="section-title">Retrieval options</div>
              <label className="label" htmlFor="vector-store">
                Vector store path (optional)
              </label>
              <input
                id="vector-store"
                className="input"
                list="known-stores"
                value={vectorStoreDir}
                onChange={(e) => setVectorStoreDir(e.target.value)}
                placeholder="./stores/td_store"
              />
              <datalist id="known-stores">
                {knownStores.map((store) => (
                  <option key={store} value={store} />
                ))}
              </datalist>
              <div className="grid two" style={{ marginTop: 10 }}>
                <label className="label" htmlFor="top-k">
                  Context top_k
                </label>
                <input
                  id="top-k"
                  className="input"
                  type="number"
                  min={1}
                  max={12}
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value, 10) || 4)}
                />
              </div>
              <div className="chip-row" style={{ marginTop: 10 }}>
                <label className="pill">
                  <input type="checkbox" checked={enableContext} onChange={(e) => setEnableContext(e.target.checked)} />{" "}
                  Context
                </label>
                <label className="pill">
                  <input type="checkbox" checked={enableSummary} onChange={(e) => setEnableSummary(e.target.checked)} />{" "}
                  Summaries
                </label>
                <label className="pill">
                  <input type="checkbox" checked={enableIntents} onChange={(e) => setEnableIntents(e.target.checked)} />{" "}
                  Intent tracking
                </label>
              </div>
              <div className="muted" style={{ marginTop: 8 }}>
                {summary}
              </div>
            </div>
          </form>
        </div>

        <div className="card">
          <div className="section-title">Past conversations</div>
          <p className="subhead">Pulled from the server memory for quick recall.</p>
          <div className="grid" style={{ gap: 10, marginTop: 10 }}>
            {currentSessions.map((sess) => (
              <button
                key={sess.session_id}
                className="button secondary"
                onClick={() => {
                  setCurrentSession(sess.session_id);
                  onSessionChange(sess.session_id);
                  loadHistory(sess.session_id);
                }}
              >
                <div style={{ fontWeight: 700 }}>{sess.session_id}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {new Date(sess.updated_at * 1000).toLocaleString()} · {sess.message_count} turns
                </div>
              </button>
            ))}
            {!currentSessions.length && <div className="muted">No server-side sessions yet.</div>}
          </div>
        </div>
      </section>

      <section className="card" aria-live="polite">
        <div className="card-header">
          <div>
            <div className="section-title">Live chat</div>
            <div className="muted">Streaming direct from /chat. Session aware with retrieval.</div>
          </div>
        </div>

        <div
          ref={chatScroller}
          style={{
            background: "rgba(0,0,0,0.35)",
            borderRadius: 14,
            padding: 16,
            maxHeight: 360,
            overflowY: "auto",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          {messages.length === 0 && <div className="muted">No messages yet. Say hello.</div>}
          {messages.map((msg, idx) => (
            <div
              key={`${msg.role}-${idx}`}
              style={{
                marginBottom: 12,
                display: "flex",
                justifyContent: msg.role === "assistant" ? "flex-start" : "flex-end",
              }}
            >
              <div
                style={{
                  background: msg.role === "assistant" ? "rgba(21,194,107,0.1)" : "rgba(255,255,255,0.08)",
                  border: `1px solid ${msg.role === "assistant" ? "rgba(21,194,107,0.3)" : "rgba(255,255,255,0.12)"}`,
                  borderRadius: 12,
                  padding: "10px 12px",
                  maxWidth: "80%",
                  whiteSpace: "pre-wrap",
                  color: "#f6fbf8",
                }}
              >
                <strong style={{ display: "block", marginBottom: 4, fontSize: 12 }}>
                  {msg.role === "assistant" ? "Assistant" : "You"}
                </strong>
                {msg.content}
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleSend} style={{ marginTop: 12 }}>
          <label className="label" htmlFor="chat-input">
            Your message
          </label>
          <textarea
            id="chat-input"
            className="textarea"
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your knowledge base or the TD middle-layer."
          />
          <div style={{ display: "flex", gap: 10, marginTop: 8, alignItems: "center" }}>
            <button type="submit" className="button" disabled={isSending}>
              {isSending ? "Streaming…" : "Send"}
            </button>
            <span className="muted">Uses /chat with streaming response.</span>
          </div>
        </form>
      </section>
    </div>
  );
}
