import { create } from "zustand";

import type { Citation, MessageItem } from "@/types";

interface ChatState {
  messages: MessageItem[];
  streaming: boolean;
  setMessages: (messages: MessageItem[]) => void;
  addUserMessage: (content: string) => void;
  startAssistantMessage: () => string;
  appendDelta: (messageId: string, delta: string) => void;
  setCitations: (messageId: string, citations: Citation[]) => void;
  setStreaming: (streaming: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  streaming: false,
  setMessages: (messages) => set({ messages }),
  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: crypto.randomUUID(),
          role: "user",
          content,
          citations: [],
          created_at: new Date().toISOString(),
        },
      ],
    })),
  startAssistantMessage: () => {
    const id = crypto.randomUUID();
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id,
          role: "assistant",
          content: "",
          citations: [],
          created_at: new Date().toISOString(),
        },
      ],
      streaming: true,
    }));
    return id;
  },
  appendDelta: (messageId, delta) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId ? { ...msg, content: msg.content + delta } : msg,
      ),
    })),
  setCitations: (messageId, citations) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId ? { ...msg, citations } : msg,
      ),
    })),
  setStreaming: (streaming) => set({ streaming }),
}));
