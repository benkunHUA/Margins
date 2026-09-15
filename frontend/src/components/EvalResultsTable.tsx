import { Fragment, useState } from "react";
import { ChevronDown } from "lucide-react";

import { useEvalRunItems } from "@/hooks/useEval";
import { cn } from "@/lib/utils";
import type { EvalItemStatus, EvalRunSummary } from "@/types";

const COLUMNS: { key: string; label: string }[] = [
  { key: "recall@5", label: "Recall@5" },
  { key: "recall@10", label: "Recall@10" },
  { key: "recall@30", label: "Recall@30" },
  { key: "mrr", label: "MRR" },
  { key: "ndcg@10", label: "nDCG@10" },
  { key: "hit", label: "重排命中" },
];

const STATUS_LABEL: Record<EvalItemStatus, string> = {
  hit: "命中",
  miss: "未命中",
  invalid: "标注失效",
  no_answer: "无答案",
  error: "错误",
};

function bar(value: number) {
  const percent = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded bg-slate-200">
        <div className="h-full bg-indigo-500" style={{ width: `${percent}%` }} />
      </div>
      <span className="font-mono text-xs text-slate-600">{value.toFixed(2)}</span>
    </div>
  );
}

function ItemsPanel({ runId, configIndex }: { runId: string; configIndex: number }) {
  const [status, setStatus] = useState<EvalItemStatus | "">("");
  const { data, isLoading } = useEvalRunItems(runId, {
    config_index: configIndex,
    item_status: status || undefined,
  });
  if (isLoading) return <p className="px-4 py-3 text-xs text-slate-400">加载逐题明细…</p>;
  if (!data) return null;
  return (
    <div className="border-t border-slate-100 bg-slate-50 px-4 py-3">
      <div className="mb-2 flex items-center gap-2 text-xs">
        {(["", "hit", "miss", "invalid", "no_answer", "error"] as const).map((value) => (
          <button
            key={value || "all"}
            type="button"
            onClick={() => setStatus(value)}
            className={cn(
              "rounded-full px-2 py-0.5",
              status === value ? "bg-slate-900 text-white" : "bg-white text-slate-500 hover:bg-slate-100",
            )}
          >
            {value === "" ? "全部" : STATUS_LABEL[value]}
          </button>
        ))}
        <span className="ml-auto text-slate-400">共 {data.total} 题</span>
      </div>
      <div className="space-y-1">
        {data.items.map((item) => (
          <details key={item.id} className="rounded-lg border border-slate-200 bg-white">
            <summary className="flex cursor-pointer items-center gap-3 px-3 py-2 text-xs">
              <span className="w-16 shrink-0 text-slate-400">{item.question_id}</span>
              <span className="min-w-0 flex-1 truncate text-slate-700">{item.category}</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5",
                  item.item_status === "hit" && "bg-emerald-100 text-emerald-700",
                  item.item_status === "miss" && "bg-amber-100 text-amber-700",
                  item.item_status === "invalid" && "bg-red-100 text-red-700",
                  item.item_status === "no_answer" && "bg-slate-100 text-slate-500",
                  item.item_status === "error" && "bg-red-100 text-red-700",
                )}
              >
                {STATUS_LABEL[item.item_status]}
                {item.relocated && item.item_status !== "invalid" ? " · 已重定位" : ""}
              </span>
              <span className="w-16 shrink-0 text-right font-mono text-slate-500">
                {item.best_rank ? `rank ${item.best_rank}` : "-"}
              </span>
            </summary>
            <div className="border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">
              <p className="font-mono">gold: {item.gold_matched.join(", ") || "-"}</p>
              {item.error && <p className="mt-1 text-red-600">{item.error}</p>}
              {item.retrieved.length > 0 && (
                <ol className="mt-1 space-y-0.5">
                  {item.retrieved.slice(0, 10).map((row) => (
                    <li key={row.chunk_id} className="truncate font-mono">
                      {row.rank}. {row.doc_title ?? "未知"} · {row.chunk_id.slice(0, 8)} ·{" "}
                      {row.score}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

export default function EvalResultsTable({ run }: { run: EvalRunSummary }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">参数组</th>
            {COLUMNS.map((column) => (
              <th key={column.key} className="px-4 py-3 font-medium">
                {column.label}
              </th>
            ))}
            <th className="px-4 py-3 font-medium">无效/无答案/错误</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {run.configs.map((config, index) => {
            const metrics = run.metrics[String(index)] ?? {};
            return (
              <Fragment key={index}>
                <tr
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => setExpanded(expanded === index ? null : index)}
                >
                  <td className="px-4 py-3 font-mono text-xs text-slate-700">
                    k{config.recall_k} / top{config.rerank_top_n} /{" "}
                    {config.relevance_threshold}
                    {config.rewrite_enabled ? "" : " · 无改写"}
                  </td>
                  {COLUMNS.map((column) => (
                    <td key={column.key} className="px-4 py-3">
                      {typeof metrics[column.key] === "number" ? bar(metrics[column.key]) : "-"}
                    </td>
                  ))}
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {metrics.invalid ?? 0} / {metrics.no_answer ?? 0} / {metrics.error ?? 0}
                  </td>
                  <td className="px-2 py-3 text-slate-400">
                    <ChevronDown
                      className={cn(
                        "size-4 transition-transform",
                        expanded === index && "rotate-180",
                      )}
                    />
                  </td>
                </tr>
                {expanded === index && (
                  <tr>
                    <td colSpan={COLUMNS.length + 3} className="p-0">
                      <ItemsPanel runId={run.id} configIndex={index} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
