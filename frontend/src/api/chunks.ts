import { request } from "@/api/client";
import type { ChunkContext } from "@/types";

export function getChunkContext(chunkId: string, radius = 1) {
  return request<ChunkContext>(`/chunks/${chunkId}/context?radius=${radius}`);
}
