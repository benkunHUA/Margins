import { FileText } from "lucide-react";

import type { Citation } from "@/types";

interface CitationCardProps {
  index: number;
  citation: Citation;
}

export default function CitationCard({ index, citation }: CitationCardProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
      <div className="flex items-center gap-1.5 font-medium text-slate-700">
        <span className="flex size-4 items-center justify-center rounded bg-slate-900 text-[10px] text-white">
          {index}
        </span>
        <FileText className="size-3.5 text-slate-400" />
        {citation.doc_title}
      </div>
      {citation.heading_path && <p className="mt-1 text-slate-400">{citation.heading_path}</p>}
      <p className="mt-1 line-clamp-3 text-slate-500">{citation.snippet}</p>
    </div>
  );
}
