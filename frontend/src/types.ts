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

export type LogStatus = "success" | "failed";

export interface TraceResultRow {
  chunk_id?: string;
  doc_title?: string;
  score?: number;
  snippet?: string;
}

export interface TraceReference {
  index?: number;
  doc_title?: string;
  heading_path?: string | null;
  snippet?: string;
}

export interface TraceData {
  queries?: string[];
  history?: { role: string; content: string }[];
  need_rewrite?: boolean;
  rewrite_type?: string | null;
  query?: string;
  dense_raw?: number;
  dense_filtered?: number;
  sparse?: number;
  fused?: number;
  top_results?: TraceResultRow[];
  candidates?: number;
  top_n?: number;
  threshold?: number;
  returned?: number;
  results?: TraceResultRow[];
  top_k?: number;
  reference_count?: number;
  references?: TraceReference[];
  prompt?: { messages?: { role?: string; content?: string }[] };
  stream_chunks?: number;
  duration_ms?: number;
  answer_excerpt?: string;
  output_tokens_estimate?: number;
}

export interface QueryLogTraceStep {
  stage: "rewrite" | "hybrid" | "rerank" | "context" | "llm";
  label: string;
  duration_ms: number;
  summary: string;
  data: TraceData;
}

export interface QueryLogSummaryItem {
  id: string;
  session_id: string;
  session_title: string;
  question: string;
  status: LogStatus;
  error: string | null;
  total_ms: number;
  citation_count: number;
  answer_excerpt: string | null;
  created_at: string;
}

export interface QueryLogDetailItem {
  id: string;
  session_id: string;
  session_title: string;
  question: string;
  status: LogStatus;
  error: string | null;
  total_ms: number;
  answer: string | null;
  steps: QueryLogTraceStep[];
  citations: Citation[];
  created_at: string;
}
