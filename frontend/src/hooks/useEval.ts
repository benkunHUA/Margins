import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createEvalRun,
  deleteEvalDataset,
  getEvalRun,
  listEvalDatasets,
  listEvalRunItems,
  listEvalRuns,
  uploadEvalDataset,
} from "@/api/eval";
import type { EvalItemStatus, EvalMode, EvalRunConfig } from "@/types";

export function useEvalDatasets() {
  return useQuery({ queryKey: ["eval-datasets"], queryFn: listEvalDatasets });
}

export function useUploadEvalDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadEvalDataset(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["eval-datasets"] }),
  });
}

export function useDeleteEvalDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteEvalDataset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["eval-datasets"] });
      queryClient.invalidateQueries({ queryKey: ["eval-runs"] });
    },
  });
}

export function useCreateEvalRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      dataset_id: string;
      mode: EvalMode;
      configs: EvalRunConfig[];
    }) => createEvalRun(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["eval-runs"] }),
  });
}

export function useEvalRuns(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["eval-runs", page, pageSize],
    queryFn: () => listEvalRuns(page, pageSize),
  });
}

export function useEvalRun(id: string | null) {
  return useQuery({
    queryKey: ["eval-run", id],
    queryFn: () => getEvalRun(id as string),
    enabled: id !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
  });
}

export function useEvalRunItems(
  runId: string | null,
  params: { config_index?: number; item_status?: EvalItemStatus; page?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ["eval-run-items", runId, params],
    queryFn: () =>
      listEvalRunItems(runId as string, {
        page: params.page ?? 1,
        page_size: 50,
        config_index: params.config_index,
        item_status: params.item_status,
      }),
    enabled: enabled && runId !== null,
  });
}
