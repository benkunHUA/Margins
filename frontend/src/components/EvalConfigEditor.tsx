import { Plus, Trash2 } from "lucide-react";

import type { EvalRunConfig } from "@/types";

interface Props {
  configs: EvalRunConfig[];
  onChange: (configs: EvalRunConfig[]) => void;
}

const DEFAULTS: EvalRunConfig = {
  recall_k: 30,
  rerank_top_n: 6,
  relevance_threshold: 0.3,
  rewrite_enabled: true,
  rerank_model: null,
};

export default function EvalConfigEditor({ configs, onChange }: Props) {
  const update = (index: number, patch: Partial<EvalRunConfig>) => {
    onChange(configs.map((config, i) => (i === index ? { ...config, ...patch } : config)));
  };

  return (
    <div className="space-y-2">
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-slate-500">
          <tr>
            <th className="py-2 font-medium">#</th>
            <th className="font-medium">RECALL_K</th>
            <th className="font-medium">RERANK_TOP_N</th>
            <th className="font-medium">阈值</th>
            <th className="font-medium">查询改写</th>
            <th className="font-medium">Rerank 模型</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {configs.map((config, index) => (
            <tr key={index} className="border-t border-slate-100">
              <td className="py-2 text-slate-400">{index + 1}</td>
              <td>
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={config.recall_k}
                  onChange={(event) => update(index, { recall_k: Number(event.target.value) })}
                  className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={config.rerank_top_n}
                  onChange={(event) =>
                    update(index, { rerank_top_n: Number(event.target.value) })
                  }
                  className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </td>
              <td>
                <input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  value={config.relevance_threshold}
                  onChange={(event) =>
                    update(index, { relevance_threshold: Number(event.target.value) })
                  }
                  className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={config.rewrite_enabled}
                  onChange={(event) =>
                    update(index, { rewrite_enabled: event.target.checked })
                  }
                />
              </td>
              <td>
                <input
                  value={config.rerank_model ?? ""}
                  placeholder="默认"
                  onChange={(event) =>
                    update(index, { rerank_model: event.target.value || null })
                  }
                  className="w-32 rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </td>
              <td className="text-right">
                <button
                  type="button"
                  disabled={configs.length <= 1}
                  onClick={() => onChange(configs.filter((_, i) => i !== index))}
                  className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"
                >
                  <Trash2 className="size-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        type="button"
        disabled={configs.length >= 5}
        onClick={() => onChange([...configs, { ...DEFAULTS }])}
        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
      >
        <Plus className="size-3.5" />
        添加参数组（最多 5 组）
      </button>
    </div>
  );
}
