import type { Citation } from "@/types";

export interface SSEHandlers {
  onMeta?: (data: { session_id: string; message_id: string }) => void;
  onCitations?: (data: { citations: Citation[] }) => void;
  onDelta?: (data: { content: string }) => void;
  onDone?: (data: { message_id: string }) => void;
  onError?: (data: { code: string; message: string }) => void;
}

export async function streamChat(
  sessionId: string,
  question: string,
  handlers: SSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`SSE 请求失败（${res.status}）`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const event =
        raw
          .split("\n")
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim() ?? "message";
      const dataLine = raw
        .split("\n")
        .find((line) => line.startsWith("data:"))
        ?.slice(5)
        .trim();
      if (!dataLine) continue;

      let data: Record<string, unknown>;
      try {
        data = JSON.parse(dataLine) as Record<string, unknown>;
      } catch {
        continue;
      }

      if (event === "meta") handlers.onMeta?.(data as never);
      else if (event === "citations") handlers.onCitations?.(data as never);
      else if (event === "delta") handlers.onDelta?.(data as never);
      else if (event === "done") handlers.onDone?.(data as never);
      else if (event === "error") handlers.onError?.(data as never);
    }
  }
}
