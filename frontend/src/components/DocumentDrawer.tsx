import { useMemo, useState } from "react";
import { Copy, FileText, ListTree, RefreshCw, X } from "lucide-react";

import MarkdownViewer from "@/components/MarkdownViewer";
import {
  useDocument,
  useDocumentChunks,
  useReparseDocument,
} from "@/hooks/useDocuments";
import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/types";

const statusLabel: Record<DocumentStatus, string> = {
  pending: "待解析",
  parsing: "解析中",
  ready: "已就绪",
  failed: "失败",
};

const statusClass: Record<DocumentStatus, string> = {
  pending: "bg-slate-100 text-slate-600",
  parsing: "bg-sky-100 text-sky-700",
  ready: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
};

interface DocumentDrawerProps {
  documentId: string | null;
  onClose: () => void;
}

export default function DocumentDrawer({ documentId, onClose }: DocumentDrawerProps) {
  const [tab, setTab] = useState<"markdown" | "chunks">("markdown");
  const [chunkQuery, setChunkQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);

  const { data: doc, isLoading: docLoading } = useDocument(documentId);
  const { data: chunks = [], isLoading: chunksLoading } = useDocumentChunks(documentId);
  const reparse = useReparseDocument();

  const filteredChunks = useMemo(() => {
    const q = chunkQuery.trim().toLowerCase();
    if (!q) return chunks;
    return chunks.filter(
      (chunk) =>
        chunk.content.toLowerCase().includes(q) ||
        (chunk.heading_path ?? "").toLowerCase().includes(q),
    );
  }, [chunks, chunkQuery]);

  if (!documentId) return null;

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const copyMarkdown = async () => {
    if (!doc?.markdown) return;
    await navigator.clipboard.writeText(doc.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const busy = doc?.status === "pending" || doc?.status === "parsing";

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div className="min-w-0">
            <h3 className="truncate text-lg font-semibold text-slate-900">
              {doc?.filename ?? "加载中…"}
            </h3>
            {doc && (
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                <span className="uppercase">{doc.file_type}</span>
                <span>{(doc.file_size / 1024 / 1024).toFixed(2)} MB</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 font-medium",
                    statusClass[doc.status],
                  )}
                >
                  {statusLabel[doc.status]}
                </span>
                <span>上传于 {new Date(doc.created_at).toLocaleString()}</span>
              </div>
            )}
            {doc?.status === "failed" && doc.parse_error && (
              <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                解析失败：{doc.parse_error}
              </p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {doc?.markdown && (
              <button
                type="button"
                onClick={copyMarkdown}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                <Copy className="size-3.5" />
                {copied ? "已复制" : "复制 Markdown"}
              </button>
            )}
            {(doc?.status === "failed" || doc?.status === "ready") && (
              <button
                type="button"
                onClick={() => reparse.mutate(documentId)}
                disabled={reparse.isPending}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                <RefreshCw className={cn("size-3.5", reparse.isPending && "animate-spin")} />
                重新解析
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <X className="size-5" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200 px-6 pt-2">
          <button
            type="button"
            onClick={() => setTab("markdown")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-t-lg px-3 py-2 text-sm font-medium",
              tab === "markdown"
                ? "border-b-2 border-slate-900 text-slate-900"
                : "text-slate-500 hover:text-slate-700",
            )}
          >
            <FileText className="size-4" />
            Markdown 预览
          </button>
          <button
            type="button"
            onClick={() => setTab("chunks")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-t-lg px-3 py-2 text-sm font-medium",
              tab === "chunks"
                ? "border-b-2 border-slate-900 text-slate-900"
                : "text-slate-500 hover:text-slate-700",
            )}
          >
            <ListTree className="size-4" />
            Chunks
            <span className="rounded-full bg-slate-100 px-1.5 text-xs text-slate-500">
              {chunks.length}
            </span>
          </button>
        </div>

        {/* 内容 */}
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          {docLoading ? (
            <p className="text-sm text-slate-400">加载中…</p>
          ) : tab === "markdown" ? (
            doc?.markdown ? (
              <MarkdownViewer content={doc.markdown} />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-400">
                {busy ? "文档正在解析，完成后即可预览 Markdown…" : "暂无 Markdown 内容"}
              </div>
            )
          ) : (
            <div className="space-y-3">
              <input
                value={chunkQuery}
                onChange={(event) => setChunkQuery(event.target.value)}
                placeholder="按内容或章节过滤…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              />
              {chunksLoading ? (
                <p className="text-sm text-slate-400">加载中…</p>
              ) : filteredChunks.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-400">
                  暂无分块
                </p>
              ) : (
                filteredChunks.map((chunk) => (
                  <div key={chunk.id} className="overflow-hidden rounded-lg border border-slate-200">
                    <button
                      type="button"
                      onClick={() => toggleExpanded(chunk.id)}
                      className="flex w-full items-center justify-between gap-3 bg-slate-50 px-3 py-2 text-left hover:bg-slate-100"
                    >
                      <span className="min-w-0 truncate text-sm font-medium text-slate-700">
                        <span className="mr-2 text-slate-400">#{chunk.chunk_index}</span>
                        {chunk.heading_path || "（无章节）"}
                      </span>
                      <span className="shrink-0 text-xs text-slate-400">
                        {chunk.token_count ?? "-"} tokens
                      </span>
                    </button>
                    {expanded.has(chunk.id) && (
                      <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap px-3 py-2 text-xs text-slate-600">
                        {chunk.content}
                      </pre>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
