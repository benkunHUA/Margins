import { useState } from "react";

import DocumentTable from "@/components/DocumentTable";
import UploadDropzone from "@/components/UploadDropzone";

export default function DocumentsPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-8">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">文档管理</h2>
        <p className="mt-1 text-sm text-slate-500">
          上传 PDF / Word / Markdown / TXT，解析入库后即可用于知识问答
        </p>
      </header>
      <UploadDropzone />
      <DocumentTable page={page} pageSize={pageSize} onPageChange={setPage} />
    </div>
  );
}
