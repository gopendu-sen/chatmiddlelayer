export type SourceType = "upload" | "local_path" | "git" | "confluence";

export interface BuildResult {
  store_name: string;
  path: string;
  uploaded_files?: string[];
}

export interface SessionSummary {
  session_id: string;
  updated_at: number;
  summary: string;
  last_message: string;
  vector_store_dir?: string | null;
  message_count: number;
  intents: string[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface HistoryResponse {
  session_id: string;
  messages: ChatMessage[];
  summary: string;
  intents: string[];
  last_context: string;
  last_retrievals: any[];
  vector_store_dir?: string | null;
  updated_at: number;
}
