import { useMemo } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import ChatConsole from "./pages/ChatConsole";
import Guide from "./pages/Guide";
import RagBuilder from "./pages/RagBuilder";
import { usePersistentState } from "./hooks/usePersistentState";
import { generateSessionId } from "./utils/session";

const navItems = [
  { to: "/", label: "RAG Builder" },
  { to: "/chat", label: "Chat Ops" },
  { to: "/guide", label: "How to Use" },
];

export default function App() {
  const location = useLocation();
  const [sessionId, setSessionId] = usePersistentState<string>("td.session", generateSessionId());
  const [knownStores, setKnownStores] = usePersistentState<string[]>("td.vectorStores", []);

  const activeLabel = useMemo(() => {
    const current = navItems.find((item) => item.to === location.pathname);
    return current?.label || "RAG Builder";
  }, [location.pathname]);

  const handleStoreCreated = (path: string) => {
    if (!path) return;
    setKnownStores((prev) => {
      const merged = new Set(prev);
      merged.add(path);
      return Array.from(merged);
    });
  };

  return (
    <div className="app-shell">
      <header className="nav">
        <div className="nav-inner">
          <div className="brand">
            <div className="brand-mark">TD</div>
            <div>
              <div style={{ fontWeight: 800, letterSpacing: "-0.02em" }}>Middle Layer</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {activeLabel}
              </div>
            </div>
          </div>
          <div className="nav-links">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          <div className="pill" aria-live="polite">
            <span style={{ background: "rgba(255,255,255,0.12)", padding: "4px 8px", borderRadius: 8 }}>
              Session
            </span>
            <span>{sessionId}</span>
            <button className="button secondary" onClick={() => setSessionId(generateSessionId())}>
              New ID
            </button>
          </div>
        </div>
      </header>

      <main className="content">
        <Routes>
          <Route
            path="/"
            element={
              <RagBuilder
                sessionId={sessionId}
                onSessionChange={setSessionId}
                onStoreCreated={handleStoreCreated}
              />
            }
          />
          <Route
            path="/chat"
            element={
              <ChatConsole
                sessionId={sessionId}
                onSessionChange={setSessionId}
                knownStores={knownStores}
                onStoreAdded={handleStoreCreated}
              />
            }
          />
          <Route path="/guide" element={<Guide />} />
        </Routes>
      </main>
    </div>
  );
}
