import { request } from "@/api/client";
import type { MessageItem, Page, SessionItem } from "@/types";

export function listSessions(params: { page?: number; page_size?: number } = {}) {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return request<Page<SessionItem>>(`/sessions${qs ? `?${qs}` : ""}`);
}

export function createSession() {
  return request<SessionItem>("/sessions", { method: "POST" });
}

export function getSession(id: string) {
  return request<{ session: SessionItem; messages: MessageItem[] }>(`/sessions/${id}`);
}

export function deleteSession(id: string) {
  return request<void>(`/sessions/${id}`, { method: "DELETE" });
}
