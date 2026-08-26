export type DocumentStatus = "pending" | "parsing" | "ready" | "failed";
export type MessageRole = "user" | "assistant";

export interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  parse_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends DocumentItem {
  markdown?: string | null;
}

export interface ChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  heading_path: string | null;
  token_count: number | null;
  page: number | null;
}

export interface SessionItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  doc_title: string;
  heading_path: string | null;
  snippet: string;
}

export interface MessageItem {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
