import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listSessions } from "@/api/sessions";
import LogDetailDrawer from "@/components/LogDetailDrawer";
import LogTable from "@/components/LogTable";
import { cn } from "@/lib/utils";
import type { LogStatus } from "@/types";

const STATUS_FILTERS: { label: string; value?: LogStatus }[] = [
  { label: "全部" },
  { label: "成功", value: "success" },
  { label: "失败", value: "failed" },
];

export default function LogsPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [q, setQ] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [status, setStatus] = useState<LogStatus | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: sessions } = useQuery({
    queryKey: ["sessions", "options"],
    queryFn: () => listSessions({ page_size: 100 }),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">链路日志</h2>
        <p className="mt-1 text-sm text-slate-500">
          每次问答的完整后端链路：查询改写 → 混合检索 → 重排序 → Prompt → 生成
        </p>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.label}
                type="button"
                onClick={() => {
                  setStatus(filter.value);
                  setPage(1);
                }}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium",
                  status === filter.value
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100",
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <select
            value={sessionId}
            onChange={(event) => {
              setSessionId(event.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
          >
            <option value="">全部会话</option>
            {(sessions?.items ?? []).map((session) => (
              <option key={session.id} value={session.id}>
                {session.title}
              </option>
            ))}
          </select>
        </div>
        <input
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          placeholder="搜索问题 / 改写查询 / 回答…"
          className="w-72 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        />
      </div>

      <LogTable
        page={page}
        pageSize={pageSize}
        q={q.trim() || undefined}
        sessionId={sessionId || undefined}
        status={status}
        onPageChange={setPage}
        onOpenDetail={setSelectedId}
      />
      <LogDetailDrawer logId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
