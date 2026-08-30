import { FormEvent, useState } from "react";
import { SendHorizonal } from "lucide-react";

import { useChat } from "@/hooks/useChat";
import { useChatStore } from "@/stores/chatStore";
import MessageBubble from "@/components/MessageBubble";

interface ChatPanelProps {
  sessionId: string;
}

export default function ChatPanel({ sessionId }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const { sendMessage } = useChat(sessionId);
  const messages = useChatStore((state) => state.messages);
  const streaming = useChatStore((state) => state.streaming);
  const lastMessageId = messages[messages.length - 1]?.id;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || streaming) return;
    setInput("");
    void sendMessage(question);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
        {messages.length === 0 ? (
          <p className="pt-16 text-center text-sm text-slate-400">向知识库提问，开始对话</p>
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              streaming={streaming && msg.id === lastMessageId}
            />
          ))
        )}
      </div>
      <form onSubmit={onSubmit} className="flex gap-2 border-t border-slate-200 p-4">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="输入问题…"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        />
        <button
          type="submit"
          disabled={!input.trim() || streaming}
          className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
        >
          <SendHorizonal className="size-4" />
          发送
        </button>
      </form>
    </div>
  );
}
