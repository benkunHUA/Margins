import { useEffect, useState } from "react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createSession, deleteSession, getSession, listSessions } from "@/api/sessions";
import ChatPanel from "@/components/ChatPanel";
import { useChatStore } from "@/stores/chatStore";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const setMessages = useChatStore((state) => state.setMessages);

  const { data: sessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => listSessions({ page_size: 50 }),
  });

  const create = useMutation({
    mutationFn: createSession,
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setSessionId(session.id);
      setMessages([]);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      if (sessionId === id) {
        setSessionId(null);
        setMessages([]);
      }
    },
  });

  useEffect(() => {
    if (sessionId) {
      getSession(sessionId)
        .then((detail) => setMessages(detail.messages))
        .catch(() => setMessages([]));
    }
  }, [sessionId, setMessages]);

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col px-8 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">知识问答</h2>
          <p className="mt-1 text-sm text-slate-500">
            基于已入库文档的多轮问答，回答附带引用来源
          </p>
        </div>
        <button
          type="button"
          onClick={() => create.mutate()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          <MessageSquarePlus className="size-4" />
          新会话
        </button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row">
        <aside className="max-h-48 w-full shrink-0 overflow-y-auto rounded-xl border border-slate-200 bg-white md:max-h-none md:w-60">
          {sessions?.items.map((session) => (
            <div
              key={session.id}
              onClick={() => setSessionId(session.id)}
              className={cn(
                "group flex cursor-pointer items-center justify-between gap-2 px-3 py-2.5 text-sm hover:bg-slate-50",
                sessionId === session.id && "bg-slate-100",
              )}
            >
              <span className="min-w-0 truncate text-slate-700">{session.title}</span>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  if (window.confirm("确定删除该会话？")) remove.mutate(session.id);
                }}
                className="shrink-0 text-slate-300 hover:text-red-500"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
        </aside>
        <div className="min-h-0 min-w-0 flex-1">
          {sessionId ? (
            <ChatPanel sessionId={sessionId} />
          ) : (
            <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-400">
              选择一个会话，或新建会话开始提问
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
