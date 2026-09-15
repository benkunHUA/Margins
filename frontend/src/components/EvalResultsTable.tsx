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

const CATEGORY_LABEL: Record<string, string> = {
  single_doc_fact: "单文档事实",
  multi_paragraph: "跨段落",
  multi_doc: "跨文档",
  table_number: "表格数字",
  no_answer: "无答案",
};

const SOURCE_LABEL: Record<string, string> = {
  chunk_id: "精确",
  snippet: "片段定位",
  keywords: "关键词定位",
  invalid: "失效",
};

function diagnosticsText(diagnostics: Record<string, number> | undefined): string {
  if (!diagnostics) return "";
  const denseRaw = diagnostics.dense_raw ?? 0;
  const denseFiltered = diagnostics.dense_filtered ?? 0;
  const sparse = diagnostics.sparse ?? 0;
  const fused = diagnostics.fused ?? 0;
  const base = `稠密 ${denseRaw} → 阈值过滤后 ${denseFiltered} ｜ 稀疏 ${sparse} ｜ 融合 ${fused}`;
  if (fused === 0 && denseRaw > 0 && denseFiltered === 0) {
    return `${base}（候选被 RELEVANCE_THRESHOLD 全部过滤）`;
  }
  if (fused === 0) return `${base}（检索无结果）`;
  return base;
}

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
              <span className="min-w-0 flex-1 truncate text-slate-700" title={item.question}>
                {item.question}
              </span>
              <span className="shrink-0 text-slate-400">
                {CATEGORY_LABEL[item.category] ?? item.category}
              </span>
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
            <div className="space-y-3 border-t border-slate-100 px-3 py-3 text-xs text-slate-600">
              <p>
                <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                  {SOURCE_LABEL[item.resolution_source] ?? item.resolution_source}
                </span>
                {item.error && <span className="text-red-600">{item.error}</span>}
              </p>

              <div>
                <p className="mb-1 font-medium text-slate-700">标注（gold）</p>
                {item.gold_matched.length === 0 ? (
                  <p className="text-slate-400">—</p>
                ) : (
                  <div className="space-y-1.5">
                    {item.gold_matched.map((gold) => (
                      <div
                        key={gold.chunk_id}
                        className="rounded-lg border border-emerald-100 bg-emerald-50/60 px-2.5 py-2"
                      >
                        <p className="font-medium text-emerald-800">
                          {gold.doc_title || "未知文档"}
                          {gold.heading_path ? ` · ${gold.heading_path}` : ""}
                        </p>
                        {gold.snippet && (
                          <p className="mt-1 text-slate-600">{gold.snippet}</p>
                        )}
                        <p className="mt-1 font-mono text-[10px] text-emerald-700">
                          {gold.chunk_id.slice(0, 8)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <p className="mb-1 font-medium text-slate-700">候选诊断</p>
                <p className="rounded-lg bg-slate-50 px-2.5 py-2 font-mono text-[11px] text-slate-600">
                  {diagnosticsText(item.diagnostics) || "（无诊断数据）"}
                </p>
              </div>

              <div>
                <p className="mb-1 font-medium text-slate-700">
                  候选列表（前 {Math.min(item.retrieved.length, 10)} 条）
                </p>
                {item.retrieved.length === 0 ? (
                  <p className="text-slate-400">无候选（召回阶段为空）</p>
                ) : (
                  <ol className="space-y-1">
                    {item.retrieved.slice(0, 10).map((row) => (
                      <li
                        key={row.chunk_id}
                        className={cn(
                          "rounded-lg border px-2.5 py-1.5",
                          row.matched
                            ? "border-emerald-200 bg-emerald-50"
                            : "border-slate-100 bg-white",
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-slate-400">#{row.rank}</span>
                          <span className="min-w-0 flex-1 truncate text-slate-700">
                            {row.doc_title ?? "未知文档"}
                            {row.heading_path ? ` · ${row.heading_path}` : ""}
                          </span>
                          <span className="font-mono text-[11px] text-indigo-600">
                            {row.score?.toFixed(3)}
                          </span>
                          {row.matched && (
                            <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-medium text-white">
                              GOLD
                            </span>
                          )}
                        </div>
                        {row.snippet && (
                          <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">
                            {row.snippet}
                          </p>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
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
