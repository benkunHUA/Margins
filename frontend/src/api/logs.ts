import { request } from "@/api/client";
import type { LogStatus, Page, QueryLogDetailItem, QueryLogSummaryItem } from "@/types";

export interface ListLogsParams {
  page?: number;
  page_size?: number;
  q?: string;
  session_id?: string;
  status?: LogStatus;
}

export function listLogs(params: ListLogsParams = {}) {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (params.q) search.set("q", params.q);
  if (params.session_id) search.set("session_id", params.session_id);
  if (params.status) search.set("status", params.status);
  const qs = search.toString();
  return request<Page<QueryLogSummaryItem>>(`/logs${qs ? `?${qs}` : ""}`);
}

export function getLog(id: string) {
  return request<QueryLogDetailItem>(`/logs/${id}`);
}
