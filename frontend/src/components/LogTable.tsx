import { Eye } from "lucide-react";

import { useLogs } from "@/hooks/useLogs";
import { cn } from "@/lib/utils";
import type { LogStatus, QueryLogSummaryItem } from "@/types";

const statusLabel: Record<LogStatus, string> = { success: "成功", failed: "失败" };
const statusClass: Record<LogStatus, string> = {
  success: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
};

export function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
}

interface LogTableProps {
  page: number;
  pageSize: number;
  q?: string;
  sessionId?: string;
  status?: LogStatus;
  onPageChange: (page: number) => void;
  onOpenDetail: (logId: string) => void;
}

export default function LogTable({
  page,
  pageSize,
  q,
  sessionId,
  status,
  onPageChange,
  onOpenDetail,
}: LogTableProps) {
  const { data, isLoading, isError } = useLogs(page, pageSize, { q, sessionId, status });

  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="flex items-center gap-4 border-b border-slate-100 px-4 py-3">
            <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
            <div className="h-3 w-1/3 animate-pulse rounded bg-slate-200" />
            <div className="h-3 w-20 animate-pulse rounded bg-slate-200" />
            <div className="ml-auto h-5 w-12 animate-pulse rounded-full bg-slate-200" />
          </div>
        ))}
      </div>
    );
  }
  if (isError) return <p className="text-sm text-red-600">日志列表加载失败</p>;
  if (!data || data.items.length === 0) {
    return (
      <p className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">
        暂无链路日志——去“知识问答”提一个问题试试
      </p>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">时间</th>
            <th className="px-4 py-3 font-medium">问题</th>
            <th className="px-4 py-3 font-medium">会话</th>
            <th className="px-4 py-3 font-medium">状态</th>
            <th className="px-4 py-3 font-medium">引用</th>
            <th className="px-4 py-3 font-medium">耗时</th>
            <th className="px-4 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.items.map((log: QueryLogSummaryItem) => (
            <tr
              key={log.id}
              onClick={() => onOpenDetail(log.id)}
              className="cursor-pointer hover:bg-slate-50"
            >
              <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                {new Date(log.created_at).toLocaleString()}
              </td>
              <td className="max-w-80 truncate px-4 py-3 font-medium text-slate-800">
                {log.question}
              </td>
              <td className="max-w-40 truncate px-4 py-3 text-slate-500">
                {log.session_title}
              </td>
              <td className="px-4 py-3">
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    statusClass[log.status],
                  )}
                >
                  {statusLabel[log.status]}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-500">{log.citation_count}</td>
              <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-500">
                {formatDuration(log.total_ms)}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenDetail(log.id);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                >
                  <Eye className="size-3.5" />
                  详情
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
        <span>共 {data.total} 条日志</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded-lg border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            上一页
          </button>
          <span className="px-2 py-1">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded-lg border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
