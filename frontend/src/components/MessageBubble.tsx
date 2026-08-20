import type { MessageItem } from "@/types";
import MarkdownViewer from "@/components/MarkdownViewer";
import CitationCard from "@/components/CitationCard";

interface MessageBubbleProps {
  message: MessageItem;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isUser
            ? "max-w-[75%] rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2.5 text-sm text-white"
            : "max-w-[85%] rounded-2xl rounded-bl-sm border border-slate-200 bg-slate-50 px-4 py-3"
        }
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            <MarkdownViewer content={message.content} />
            {message.citations.length > 0 && (
              <div className="mt-3 space-y-2 border-t border-slate-200 pt-3">
                {message.citations.map((citation, index) => (
                  <CitationCard key={citation.chunk_id} index={index + 1} citation={citation} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
