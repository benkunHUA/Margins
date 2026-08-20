import { useCallback } from "react";

import { streamChat } from "@/api/sse";
import { useChatStore } from "@/stores/chatStore";

export function useChat(sessionId: string) {
  const setCitations = useChatStore((state) => state.setCitations);
  const setStreaming = useChatStore((state) => state.setStreaming);

  const sendMessage = useCallback(
    async (question: string) => {
      const addUserMessage = useChatStore.getState().addUserMessage;
      const startAssistantMessage = useChatStore.getState().startAssistantMessage;

      addUserMessage(question);
      const messageId = startAssistantMessage();
      setStreaming(true);

      try {
        await streamChat(sessionId, question, {
          onCitations: (data) => setCitations(messageId, data.citations),
          onDelta: (data) => {
            const appendDelta = useChatStore.getState().appendDelta;
            appendDelta(messageId, data.content);
          },
          onError: (data) => {
            const appendDelta = useChatStore.getState().appendDelta;
            appendDelta(messageId, `\n\n> 错误：${data.message}`);
          },
        });
      } catch (error) {
        const appendDelta = useChatStore.getState().appendDelta;
        appendDelta(messageId, `\n\n> 请求失败：${(error as Error).message}`);
      } finally {
        setStreaming(false);
      }
    },
    [sessionId, setCitations, setStreaming],
  );

  return { sendMessage };
}
