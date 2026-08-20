import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteDocument, listDocuments, uploadDocuments } from "@/api/documents";
import { useDocumentStore } from "@/stores/documentStore";

export function useDocuments(page = 1, pageSize = 20) {
  const keyword = useDocumentStore((state) => state.keyword);
  return useQuery({
    queryKey: ["documents", page, pageSize, keyword],
    queryFn: () => listDocuments({ page, page_size: pageSize, q: keyword || undefined }),
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
