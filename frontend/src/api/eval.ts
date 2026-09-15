import { request } from "@/api/client";
import type {
  EvalDatasetSummary,
  EvalItemStatus,
  EvalMode,
  EvalRunConfig,
  EvalRunItem,
  EvalRunSummary,
  Page,
} from "@/types";

export function listEvalDatasets() {
  return request<Page<EvalDatasetSummary>>("/eval/datasets");
}

export function uploadEvalDataset(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<EvalDatasetSummary>("/eval/datasets", {
    method: "POST",
    body: form,
  });
}

export function deleteEvalDataset(id: string) {
  return request<void>(`/eval/datasets/${id}`, { method: "DELETE" });
}

export function createEvalRun(body: {
  dataset_id: string;
  mode: EvalMode;
  configs: EvalRunConfig[];
}) {
  return request<EvalRunSummary>("/eval/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function listEvalRuns(page = 1, pageSize = 20) {
  return request<Page<EvalRunSummary>>(`/eval/runs?page=${page}&page_size=${pageSize}`);
}

export function getEvalRun(id: string) {
  return request<EvalRunSummary>(`/eval/runs/${id}`);
}

export function listEvalRunItems(
  runId: string,
  params: {
    page?: number;
    page_size?: number;
    config_index?: number;
    item_status?: EvalItemStatus;
    relocated?: boolean;
  } = {},
) {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (params.config_index !== undefined)
    search.set("config_index", String(params.config_index));
  if (params.item_status) search.set("item_status", params.item_status);
  if (params.relocated !== undefined) search.set("relocated", String(params.relocated));
  const qs = search.toString();
  return request<Page<EvalRunItem>>(`/eval/runs/${runId}/items${qs ? `?${qs}` : ""}`);
}
