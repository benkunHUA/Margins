import { useQuery } from "@tanstack/react-query";

import { getChunkContext } from "@/api/chunks";

export function useChunkContext(chunkId: string | null, radius = 1) {
  return useQuery({
    queryKey: ["chunk-context", chunkId, radius],
    queryFn: () => getChunkContext(chunkId as string, radius),
    enabled: chunkId !== null,
    retry: false, // 引用失效（404）要立刻显示提示，不要重试
  });
}
