import { useEffect, useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

import { useUploadDocuments } from "@/hooks/useDocuments";
import { cn } from "@/lib/utils";

const ACCEPTED = ".pdf,.docx,.md,.txt";
const ALLOWED_EXTENSIONS = ["pdf", "docx", "md", "txt"];

export default function UploadDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const upload = useUploadDocuments();

  useEffect(() => {
    if (!upload.isSuccess) return;
    setSuccessMessage(`已上传 ${upload.data.length} 个文件，开始解析…`);
    const timer = setTimeout(() => setSuccessMessage(null), 6000);
    return () => clearTimeout(timer);
  }, [upload.isSuccess, upload.data]);

  const handleFiles = (files: File[]) => {
    if (files.length === 0) return;
    const valid = files.filter((file) =>
      ALLOWED_EXTENSIONS.includes(file.name.split(".").pop()?.toLowerCase() ?? ""),
    );
    setValidationError(
      valid.length !== files.length ? "包含不支持的文件类型（仅支持 PDF / Word / Markdown / TXT）" : null,
    );
    if (valid.length === 0) return;
    upload.mutate(valid);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        handleFiles(Array.from(event.dataTransfer.files));
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
        dragging ? "border-sky-500 bg-sky-50" : "border-slate-300 bg-white hover:border-sky-400 hover:bg-slate-50",
      )}
    >
      <UploadCloud className="size-8 text-slate-400" />
      <p className="mt-3 text-sm font-medium text-slate-600">拖拽文件到此处，或点击选择文件</p>
      <p className="mt-1 text-xs text-slate-400">支持 PDF / Word / Markdown / TXT，单文件不超过 100MB</p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        multiple
        className="hidden"
        onChange={(event) => {
          handleFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      {upload.isPending && <p className="mt-3 text-xs text-sky-600">正在上传…</p>}
      {successMessage && <p className="mt-3 text-xs text-emerald-600">{successMessage}</p>}
      {validationError && <p className="mt-3 text-xs text-red-600">{validationError}</p>}
      {upload.isError && <p className="mt-3 text-xs text-red-600">{upload.error.message}</p>}
    </div>
  );
}
