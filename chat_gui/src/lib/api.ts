import { BuildResult, HistoryResponse, SessionSummary } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8010";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) {
    return {} as T;
  }
  return (await response.json()) as T;
}

export async function buildVectorStoreFromPath(payload: unknown): Promise<BuildResult> {
  const res = await fetch(`${API_BASE}/vector-store/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<BuildResult>(res);
}

export async function buildVectorStoreWithUpload(formData: FormData): Promise<BuildResult> {
  const res = await fetch(`${API_BASE}/vector-store/build/upload`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<BuildResult>(res);
}

export async function fetchHistory(sessionId: string): Promise<HistoryResponse> {
  const res = await fetch(`${API_BASE}/chat/history/${encodeURIComponent(sessionId)}`);
  return handleResponse<HistoryResponse>(res);
}

export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_BASE}/chat/sessions`);
  const data = await handleResponse<{ sessions: SessionSummary[] }>(res);
  return data.sessions || [];
}

export async function queryVectorStore(payload: unknown): Promise<any> {
  const res = await fetch(`${API_BASE}/vector-store/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<any>(res);
}
