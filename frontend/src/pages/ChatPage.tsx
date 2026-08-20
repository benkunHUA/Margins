import { useEffect, useState } from "react";

import { createSession } from "@/api/sessions";
import ChatPanel from "@/components/ChatPanel";

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    createSession()
      .then((session) => {
        if (!cancelled) setSessionId(session.id);
      })
      .catch(() => {
        if (!cancelled) setSessionId("local-fallback");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col px-8 py-8">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold tracking-tight">知识问答</h2>
        <p className="mt-1 text-sm text-slate-500">基于已入库文档的多轮问答，回答附带引用来源</p>
      </header>
      {sessionId ? <ChatPanel sessionId={sessionId} /> : <p className="text-slate-400">正在创建会话…</p>}
    </div>
  );
}
