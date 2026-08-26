import { useState } from "react";

import DocumentDrawer from "@/components/DocumentDrawer";
import DocumentTable from "@/components/DocumentTable";
import UploadDropzone from "@/components/UploadDropzone";
import { useDocumentStore } from "@/stores/documentStore";
import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/types";

const FILTERS: { label: string; value?: DocumentStatus }[] = [
  { label: "全部" },
  { label: "待解析", value: "pending" },
  { label: "解析中", value: "parsing" },
  { label: "已就绪", value: "ready" },
  { label: "失败", value: "failed" },
];

export default function DocumentsPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [status, setStatus] = useState<DocumentStatus | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const keyword = useDocumentStore((state) => state.keyword);
  const setKeyword = useDocumentStore((state) => state.setKeyword);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">文档管理</h2>
        <p className="mt-1 text-sm text-slate-500">
          上传 PDF / Word / Markdown / TXT，解析入库后即可用于知识问答
        </p>
      </header>
      <UploadDropzone />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              onClick={() => {
                setStatus(filter.value);
                setPage(1);
              }}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium",
                status === filter.value
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100",
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <input
          value={keyword}
          onChange={(event) => {
            setKeyword(event.target.value);
            setPage(1);
          }}
          placeholder="搜索文件名…"
          className="w-56 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        />
      </div>
      <DocumentTable
        page={page}
        pageSize={pageSize}
        status={status}
        onPageChange={setPage}
        onOpenDetail={setSelectedId}
      />
      <DocumentDrawer documentId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
