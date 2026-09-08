import { request } from "@/api/client";
import type {
  ChunkItem,
  DocumentDetail,
  DocumentItem,
  DocumentStatus,
  Page,
  ParseMode,
} from "@/types";

export interface ListDocumentsParams {
  page?: number;
  page_size?: number;
  status?: DocumentStatus;
  q?: string;
}

export function listDocuments(params: ListDocumentsParams = {}) {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (params.status) search.set("status", params.status);
  if (params.q) search.set("q", params.q);
  const qs = search.toString();
  return request<Page<DocumentItem>>(`/documents${qs ? `?${qs}` : ""}`);
}

export function getDocument(id: string) {
  return request<DocumentDetail>(`/documents/${id}`);
}

export function getDocumentChunks(id: string) {
  return request<ChunkItem[]>(`/documents/${id}/chunks`);
}

export async function uploadDocuments(files: File[], parseMode: ParseMode = "mineru") {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  form.append("parse_mode", parseMode);
  return request<
    { document_id: string; filename: string; status: DocumentStatus; parse_mode: ParseMode }[]
  >(
    "/documents",
    { method: "POST", body: form },
  );
}

export function deleteDocument(id: string) {
  return request<void>(`/documents/${id}`, { method: "DELETE" });
}

export function reparseDocument(id: string, parseMode?: ParseMode) {
  return request<{ job_id: string; status: string; parse_mode: ParseMode }>(
    `/documents/${id}/reparse`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parse_mode: parseMode }),
    },
  );
}
