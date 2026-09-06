import { useEffect, useMemo, useState } from "react";
import {
  Braces,
  Check,
  ChevronDown,
  Copy,
  PenLine,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import CitationCard from "@/components/CitationCard";
import { formatDuration } from "@/components/LogTable";
import { useLog } from "@/hooks/useLogs";
import { cn } from "@/lib/utils";
import type { QueryLogTraceStep, TraceResultRow } from "@/types";

const STAGE_META = {
  rewrite: {
    label: "查询改写",
    color: "bg-indigo-500",
    soft: "bg-indigo-50 text-indigo-700",
    Icon: PenLine,
  },
  hybrid: {
    label: "混合检索",
    color: "bg-sky-500",
    soft: "bg-sky-50 text-sky-700",
    Icon: Search,
  },
  rerank: {
    label: "重排序",
    color: "bg-amber-500",
    soft: "bg-amber-50 text-amber-700",
    Icon: Braces,
  },
  context: {
    label: "上下文与 Prompt",
    color: "bg-emerald-500",
    soft: "bg-emerald-50 text-emerald-700",
    Icon: Braces,
  },
  llm: {
    label: "LLM 生成",
    color: "bg-violet-500",
    soft: "bg-violet-50 text-violet-700",
    Icon: Sparkles,
  },
} as const;

interface StepGroup {
  stage: keyof typeof STAGE_META;
  label: string;
  items: QueryLogTraceStep[];
}

function groupSteps(steps: QueryLogTraceStep[]): StepGroup[] {
  const groups: StepGroup[] = [];
  for (const step of steps) {
    const last = groups[groups.length - 1];
    if (last && last.stage === step.stage) {
      last.items.push(step);
    } else {
      groups.push({
        stage: step.stage as StepGroup["stage"],
        label: step.label,
        items: [step],
      });
    }
  }
  return groups;
}

function ResultsRows({ rows }: { rows?: TraceResultRow[] }) {
  if (!rows || rows.length === 0) return <p className="text-xs text-slate-400">（无结果）</p>;
  return (
    <ul className="space-y-2">
      {rows.map((row, index) => (
        <li
          key={`${row.chunk_id ?? index}`}
          className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
        >
          <div className="flex items-center justify-between gap-3">
            <span className="truncate text-xs font-medium text-slate-700">
              {row.doc_title ?? "未知文档"}
            </span>
            {row.score !== undefined && (
              <span className="shrink-0 font-mono text-[11px] text-indigo-600">
                {row.score.toFixed(3)}
              </span>
            )}
          </div>
          {row.snippet && (
            <p className="mt-1 line-clamp-2 text-[11px] text-slate-500">{row.snippet}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

interface LogDetailDrawerProps {
  logId: string | null;
  onClose: () => void;
}

export default function LogDetailDrawer({ logId, onClose }: LogDetailDrawerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const { data: log, isLoading, isError } = useLog(logId);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const groups = useMemo(() => groupSteps(log?.steps ?? []), [log?.steps]);
  const promptMessages = log?.steps.find((step) => step.stage === "context")?.data.prompt
    ?.messages;
  const promptText =
    promptMessages
      ?.map((message) => `${message.role ?? ""}: ${message.content ?? ""}`)
      .join("\n\n---\n\n") ?? "";

  if (!logId) return null;

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const copyPrompt = async () => {
    if (!promptText) return;
    await navigator.clipboard.writeText(promptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/40" onClick={onClose}>
      <aside
        className="flex h-full w-full flex-col bg-slate-50 shadow-2xl sm:max-w-4xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h3 className="truncate text-lg font-semibold text-slate-900">
                {log?.question ?? "加载中…"}
              </h3>
              {log && (
                <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span>{log.session_title || "（无会话标题）"}</span>
                  <span>{new Date(log.created_at).toLocaleString()}</span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 font-medium",
                      log.status === "success"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-red-100 text-red-700",
                    )}
                  >
                    {log.status === "success" ? "成功" : "失败"}
                  </span>
                  <span className="font-mono">{formatDuration(log.total_ms)}</span>
                  <span>{log.citations.length} 条引用</span>
                </div>
              )}
              {log?.status === "failed" && log.error && (
                <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                  失败原因：{log.error}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <X className="size-5" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {isLoading && <p className="text-sm text-slate-400">加载中…</p>}
          {isError && <p className="text-sm text-red-600">日志详情加载失败</p>}
          {log && (
            <div className="space-y-4">
              <div className="flex flex-col gap-1">
                {groups.map((group, groupIndex) => {
                  const meta = STAGE_META[group.stage];
                  const key = `${groupIndex}-${group.stage}`;
                  const open = expanded.has(key);
                  const totalMs = group.items.reduce((sum, item) => sum + item.duration_ms, 0);
                  const Icon = meta.Icon;
                  return (
                    <div key={key} className="relative flex gap-3">
                      <div className="flex w-5 flex-col items-center">
                        <span className={cn("z-10 mt-1 size-3 rounded-full ring-4 ring-slate-50", meta.color)} />
                        {groupIndex < groups.length - 1 && (
                          <span className="w-0.5 flex-1 bg-slate-200" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1 pb-3">
                        <button
                          type="button"
                          onClick={() => toggle(key)}
                          className="flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-left shadow-sm hover:border-slate-300"
                        >
                          <Icon className="size-4 text-slate-400" />
                          <span className="text-sm font-semibold text-slate-800">
                            {group.label}
                          </span>
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[11px] font-medium",
                              meta.soft,
                            )}
                          >
                            {group.items.length > 1
                              ? `${group.items.length} 个查询`
                              : formatDuration(totalMs)}
                          </span>
                          <span className="ml-auto truncate text-xs text-slate-400">
                            {group.items[0]?.summary}
                          </span>
                          <ChevronDown
                            className={cn(
                              "size-4 shrink-0 text-slate-400 transition-transform",
                              open && "rotate-180",
                            )}
                          />
                        </button>
                        {open && (
                          <div className="mt-2 space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                            {group.items.map((step, index) => (
                              <div key={index} className="space-y-2">
                                {group.items.length > 1 && (
                                  <p className="text-xs font-medium text-slate-500">
                                    Query {index + 1}：{String(step.data.query ?? "")}
                                  </p>
                                )}
                                {group.stage === "rewrite" && (
                                  <div className="space-y-2 text-xs text-slate-600">
                                    <p>
                                      改写类型：
                                      <span className="ml-1 rounded bg-indigo-50 px-1.5 py-0.5 font-medium text-indigo-700">
                                        {step.data.need_rewrite
                                          ? step.data.rewrite_type ?? "改写"
                                          : "无需改写"}
                                      </span>
                                    </p>
                                    <ul className="space-y-1 font-mono text-slate-700">
                                      {(step.data.queries ?? []).map((query, qi) => (
                                        <li key={qi} className="rounded bg-slate-50 px-2 py-1">
                                          → {query}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {group.stage === "hybrid" && (
                                  <div className="space-y-2">
                                    <p className="text-xs text-slate-600">
                                      稠密 {step.data.dense_filtered ?? 0} / 稀疏{" "}
                                      {step.data.sparse ?? 0} → 融合 {step.data.fused ?? 0} 条（
                                      {formatDuration(step.duration_ms)}）
                                    </p>
                                    <ResultsRows rows={step.data.top_results} />
                                  </div>
                                )}
                                {group.stage === "rerank" && (
                                  <div className="space-y-2">
                                    <p className="text-xs text-slate-600">
                                      {step.data.candidates ?? 0} 候选 → top{" "}
                                      {step.data.returned ?? 0}（阈值{" "}
                                      {step.data.threshold ?? "-"}，{formatDuration(step.duration_ms)}）
                                    </p>
                                    <ResultsRows rows={step.data.results} />
                                  </div>
                                )}
                                {group.stage === "context" && (
                                  <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                      <p className="text-xs text-slate-600">
                                        引用 {step.data.reference_count ?? 0} 条 / top_k{" "}
                                        {step.data.top_k ?? 0}
                                      </p>
                                      {promptText && (
                                        <button
                                          type="button"
                                          onClick={copyPrompt}
                                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
                                        >
                                          {copied ? (
                                            <Check className="size-3.5 text-emerald-600" />
                                          ) : (
                                            <Copy className="size-3.5" />
                                          )}
                                          {copied ? "已复制" : "复制 Prompt"}
                                        </button>
                                      )}
                                    </div>
                                    <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-100">
                                      {promptText || "（无 Prompt 内容）"}
                                    </pre>
                                  </div>
                                )}
                                {group.stage === "llm" && (
                                  <div className="space-y-2 text-xs text-slate-600">
                                    <p>
                                      {step.data.stream_chunks ?? 0} 个流式块 ·{" "}
                                      {formatDuration(step.duration_ms)}
                                    </p>
                                    {step.data.answer_excerpt && (
                                      <p className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600">
                                        {step.data.answer_excerpt}
                                      </p>
                                    )}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <h4 className="text-sm font-semibold text-slate-800">完整回答</h4>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                  {log.answer || "（失败或空回答）"}
                </p>
              </section>
              {log.citations.length > 0 && (
                <section className="rounded-xl border border-slate-200 bg-white p-4">
                  <h4 className="text-sm font-semibold text-slate-800">
                    引用 {log.citations.length} 条
                  </h4>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    {log.citations.map((citation, index) => (
                      <CitationCard key={citation.chunk_id} index={index + 1} citation={citation} />
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
