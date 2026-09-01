import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteDocument,
  getDocument,
  getDocumentChunks,
  listDocuments,
  reparseDocument,
  uploadDocuments,
} from "@/api/documents";
import { useDocumentStore } from "@/stores/documentStore";
import type { DocumentStatus } from "@/types";

export function useDocuments(page = 1, pageSize = 20, status?: DocumentStatus) {
  const keyword = useDocumentStore((state) => state.keyword);
  const { data, refetch, isLoading, isError } = useQuery({
    queryKey: ["documents", page, pageSize, keyword, status],
    queryFn: () =>
      listDocuments({ page, page_size: pageSize, q: keyword || undefined, status }),
  });
  const hasActive = (data?.items ?? []).some(
    (doc) => doc.status === "pending" || doc.status === "parsing",
  );

  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => {
      void refetch();
    }, 2000);
    return () => clearInterval(timer);
  }, [hasActive, refetch]);

  return { data, isLoading, isError };
}

export function useDocument(id: string | null) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => getDocument(id as string),
    enabled: id !== null,
  });
}

export function useDocumentChunks(id: string | null) {
  return useQuery({
    queryKey: ["document-chunks", id],
    queryFn: () => getDocumentChunks(id as string),
    enabled: id !== null,
  });
}

export function useUploadDocuments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => uploadDocuments(files),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useReparseDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reparseDocument(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document", id] });
      queryClient.invalidateQueries({ queryKey: ["document-chunks", id] });
    },
  });
}
