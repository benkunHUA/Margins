import { useEffect, useRef } from "react";
import { AlertTriangle, FileText, X } from "lucide-react";

import { ApiError } from "@/api/client";
import MarkdownViewer from "@/components/MarkdownViewer";
import { useChunkContext } from "@/hooks/useChunks";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types";

interface ChunkContextDialogProps {
  citation: Citation;
  onClose: () => void;
}

export default function ChunkContextDialog({ citation, onClose }: ChunkContextDialogProps) {
  const { data, isLoading, error } = useChunkContext(citation.chunk_id);
  const focusRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (data) focusRef.current?.scrollIntoView({ block: "start" });
  }, [data]);

  const missing = error instanceof ApiError && error.status === 404;
  const heading = data?.heading_path ?? citation.heading_path;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`引用预览：${citation.doc_title}`}
        className="flex max-h-[80vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-sm font-medium text-slate-800">
              <FileText className="size-4 shrink-0 text-slate-400" />
              <span className="truncate">{citation.doc_title}</span>
            </div>
            {heading && <p className="mt-0.5 truncate text-xs text-slate-400">{heading}</p>}
            {data && (
              <p className="mt-0.5 text-xs text-slate-500">
                第 {data.chunk_index + 1}/{data.chunk_total} 块
              </p>
            )}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {isLoading && (
            <div className="space-y-2" aria-busy="true">
              {[0, 1, 2].map((row) => (
                <div key={row} className="h-4 animate-pulse rounded bg-slate-100" />
              ))}
            </div>
          )}

          {missing && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <p>该引用已失效——文档可能已重新解析，可在文档管理页查看最新内容。</p>
            </div>
          )}

          {error && !missing && <p className="text-xs text-red-600">加载失败：{error.message}</p>}

          {data?.items.map((item) => (
            <div
              key={item.chunk_id}
              ref={item.is_focus ? focusRef : undefined}
              className={cn(
                "rounded-lg border px-3 py-2",
                item.is_focus
                  ? "border-sky-200 bg-sky-50/60 ring-1 ring-sky-200"
                  : "border-slate-200 bg-white",
              )}
            >
              <p className="mb-1 text-[11px] text-slate-400">
                {item.is_focus ? "引用块 · " : ""}
                第 {item.chunk_index + 1} 块
                {!item.is_focus && item.heading_path ? ` · ${item.heading_path}` : ""}
              </p>
              <MarkdownViewer content={item.content} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
