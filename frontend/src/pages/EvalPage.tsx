import { useState } from "react";
import { ClipboardCheck, Play, Upload } from "lucide-react";

import EvalConfigEditor from "@/components/EvalConfigEditor";
import EvalResultsTable from "@/components/EvalResultsTable";
import {
  useCreateEvalRun,
  useDeleteEvalDataset,
  useEvalDatasets,
  useEvalRun,
  useEvalRuns,
  useUploadEvalDataset,
} from "@/hooks/useEval";
import { cn } from "@/lib/utils";
import type { EvalMode, EvalRunConfig } from "@/types";

export default function EvalPage() {
  const [datasetId, setDatasetId] = useState("");
  const [mode, setMode] = useState<EvalMode>("retrieval");
  const [configs, setConfigs] = useState<EvalRunConfig[]>([
    {
      recall_k: 30,
      rerank_top_n: 6,
      relevance_threshold: 0.3,
      rewrite_enabled: true,
      rerank_model: null,
    },
  ]);
  const [runId, setRunId] = useState<string | null>(null);

  const datasets = useEvalDatasets();
  const upload = useUploadEvalDataset();
  const removeDataset = useDeleteEvalDataset();
  const createRun = useCreateEvalRun();
  const runs = useEvalRuns();
  const run = useEvalRun(runId);
  const dataset = datasets.data?.items.find((item) => item.id === datasetId);

  const start = () => {
    if (!datasetId) return;
    createRun.mutate(
      { dataset_id: datasetId, mode, configs },
      { onSuccess: (created) => setRunId(created.id) },
    );
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 px-8 py-8">
      <header>
        <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ClipboardCheck className="size-5 text-slate-400" />
          评估
        </h2>
        <p className="mt-1 text-sm text-slate-500">用黄金集评估检索质量，多组参数批量对比</p>
      </header>

      <section className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
        <span className="text-sm font-medium text-slate-600">黄金集</span>
        <select
          value={datasetId}
          onChange={(event) => setDatasetId(event.target.value)}
          className="min-w-52 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        >
          <option value="">选择数据集…</option>
          {(datasets.data?.items ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}（{item.item_count} 题）
            </option>
          ))}
        </select>
        <label className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
          <Upload className="size-3.5" />
          导入 JSON
          <input
            type="file"
            accept=".json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.target.value = "";
            }}
          />
        </label>
        {datasetId && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm("删除该黄金集及其历史评估记录？")) {
                removeDataset.mutate(datasetId);
                setDatasetId("");
              }
            }}
            className="rounded-lg px-2.5 py-1.5 text-xs text-red-500 hover:bg-red-50"
          >
            删除
          </button>
        )}
        {dataset && (
          <span className="ml-auto text-xs text-slate-400">
            题目 {dataset.item_count} · 类别{" "}
            {Object.entries(dataset.category_counts)
              .map(([key, value]) => `${key}:${value}`)
              .join(" / ")}
          </span>
        )}
      </section>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-600">模式</span>
          {(["retrieval", "full"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium",
                mode === value ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
              )}
            >
              {value === "retrieval" ? "检索模式（快）" : "完整模式（含生成）"}
            </button>
          ))}
          <span className="ml-auto text-xs text-slate-400">
            预计调用：改写{" "}
            {configs.some((config) => config.rewrite_enabled) ? dataset?.item_count ?? 0 : 0} 次
            {mode === "full" ? ` · 生成 ${(dataset?.item_count ?? 0) * configs.length} 次` : ""}
          </span>
        </div>
        <EvalConfigEditor configs={configs} onChange={setConfigs} />
        <button
          type="button"
          disabled={!datasetId || createRun.isPending}
          onClick={start}
          className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
        >
          <Play className="size-4" />
          开始评估
        </button>
        {createRun.isError && <p className="text-xs text-red-600">{createRun.error.message}</p>}
        {upload.isError && <p className="text-xs text-red-600">{upload.error.message}</p>}
      </section>

      {run.data && (
        <section className="space-y-3">
          <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
            <span className="text-slate-600">
              {run.data.status === "running" || run.data.status === "queued"
                ? `评估中 ${run.data.progress_done}/${run.data.progress_total}`
                : run.data.status === "succeeded"
                  ? "评估完成"
                  : `评估失败：${run.data.error ?? ""}`}
            </span>
            {run.data.status === "running" || run.data.status === "queued" ? (
              <div className="h-1.5 w-40 overflow-hidden rounded bg-slate-200">
                <div
                  className="h-full bg-indigo-500"
                  style={{
                    width: `${
                      run.data.progress_total
                        ? (run.data.progress_done / run.data.progress_total) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            ) : null}
          </div>
          {run.data.status === "succeeded" && <EvalResultsTable run={run.data} />}
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-4 py-2 text-xs font-medium text-slate-500">
          历史评估
        </div>
        <div className="divide-y divide-slate-50">
          {(runs.data?.items ?? []).slice(0, 10).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setRunId(item.id)}
              className="flex w-full items-center gap-3 px-4 py-2 text-left text-xs hover:bg-slate-50"
            >
              <span className="text-slate-500">{new Date(item.created_at).toLocaleString()}</span>
              <span className="text-slate-700">
                {item.mode === "retrieval" ? "检索" : "完整"}
              </span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5",
                  item.status === "succeeded" && "bg-emerald-100 text-emerald-700",
                  item.status === "running" && "bg-sky-100 text-sky-700",
                  item.status === "failed" && "bg-red-100 text-red-700",
                )}
              >
                {item.status}
              </span>
            </button>
          ))}
          {(runs.data?.items ?? []).length === 0 && (
            <p className="px-4 py-6 text-center text-xs text-slate-400">暂无评估记录</p>
          )}
        </div>
        </section>
      </div>
    </div>
  );
}
