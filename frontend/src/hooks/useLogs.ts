import { useQuery } from "@tanstack/react-query";

import { getLog, listLogs } from "@/api/logs";
import type { LogStatus } from "@/types";

export function useLogs(
  page: number,
  pageSize: number,
  filters: { q?: string; sessionId?: string; status?: LogStatus } = {},
) {
  const q = filters.q?.trim() || undefined;
  const sessionId = filters.sessionId || undefined;
  const status = filters.status || undefined;
  return useQuery({
    queryKey: ["logs", page, pageSize, q, sessionId, status],
    queryFn: () =>
      listLogs({
        page,
        page_size: pageSize,
        q,
        session_id: sessionId,
        status,
      }),
  });
}

export function useLog(id: string | null) {
  return useQuery({
    queryKey: ["log", id],
    queryFn: () => getLog(id as string),
    enabled: id !== null,
  });
}
