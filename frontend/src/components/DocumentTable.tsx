import { Eye, Trash2 } from "lucide-react";

import { useDeleteDocument, useDocuments } from "@/hooks/useDocuments";
import { cn } from "@/lib/utils";
import type { DocumentItem, DocumentStatus } from "@/types";

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

interface DocumentTableProps {
  page: number;
  pageSize: number;
  status?: DocumentStatus;
  onPageChange: (page: number) => void;
  onOpenDetail: (docId: string) => void;
}

export default function DocumentTable({
  page,
  pageSize,
  status,
  onPageChange,
  onOpenDetail,
}: DocumentTableProps) {
  const { data, isLoading, isError } = useDocuments(page, pageSize, status);
  const remove = useDeleteDocument();

  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="divide-y divide-slate-100">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="flex items-center gap-4 px-4 py-3">
              <div className="h-3 w-1/3 animate-pulse rounded bg-slate-200" />
              <div className="h-3 w-12 animate-pulse rounded bg-slate-200" />
              <div className="h-3 w-16 animate-pulse rounded bg-slate-200" />
              <div className="ml-auto h-5 w-14 animate-pulse rounded-full bg-slate-200" />
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (isError) return <p className="text-sm text-red-600">文档列表加载失败</p>;
  if (!data || data.items.length === 0) {
    return <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-400">暂无文档</p>;
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  const handleDelete = (doc: DocumentItem) => {
    if (window.confirm(`确定删除「${doc.filename}」？将同时移除其分块与向量索引。`)) {
      remove.mutate(doc.id);
    }
  };

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">文件名</th>
            <th className="px-4 py-3 font-medium">类型</th>
            <th className="px-4 py-3 font-medium">大小</th>
            <th className="px-4 py-3 font-medium">状态</th>
            <th className="px-4 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.items.map((doc) => (
            <tr
              key={doc.id}
              onClick={() => onOpenDetail(doc.id)}
              className="cursor-pointer hover:bg-slate-50"
            >
              <td className="px-4 py-3 font-medium text-slate-800">{doc.filename}</td>
              <td className="px-4 py-3 text-slate-500">{doc.file_type.toUpperCase()}</td>
              <td className="px-4 py-3 text-slate-500">{(doc.file_size / 1024 / 1024).toFixed(1)} MB</td>
              <td className="px-4 py-3">
                <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", statusClass[doc.status])}>
                  {statusLabel[doc.status]}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenDetail(doc.id);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                >
                  <Eye className="size-3.5" />
                  详情
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleDelete(doc);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="size-3.5" />
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
        <span>共 {data.total} 份文档</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded-lg border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            上一页
          </button>
          <span className="px-2 py-1">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded-lg border border-slate-200 px-3 py-1 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
