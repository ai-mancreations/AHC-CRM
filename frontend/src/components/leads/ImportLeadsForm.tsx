import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Branch } from "@/types";
import { UploadCloud, CheckCircle2 } from "lucide-react";

interface ImportResult {
  id: string;
  total_rows: number;
  imported_count: number;
  duplicate_count: number;
  error_count: number;
}

export function ImportLeadsForm({ branches, defaultBranchId, onDone }: {
  branches: Branch[];
  defaultBranchId?: string | null;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [branchId, setBranchId] = useState(defaultBranchId ?? branches[0]?.id ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const importCsv = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      formData.append("branch_id", branchId);
      formData.append("file", file as File);
      const { data } = await api.post<ImportResult>("/leads/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? "Import failed"),
  });

  if (result) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-emerald-400">
          <CheckCircle2 size={20} />
          <span className="font-medium">Import complete</span>
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="card p-3 text-center">
            <div className="text-neutral-500 text-xs">Rows</div>
            <div className="text-lg text-neutral-200">{result.total_rows}</div>
          </div>
          <div className="card p-3 text-center">
            <div className="text-neutral-500 text-xs">Imported</div>
            <div className="text-lg text-emerald-400">{result.imported_count}</div>
          </div>
          <div className="card p-3 text-center">
            <div className="text-neutral-500 text-xs">Duplicates</div>
            <div className="text-lg text-amber-400">{result.duplicate_count}</div>
          </div>
        </div>
        {result.error_count > 0 && (
          <div className="text-xs text-red-400">{result.error_count} row(s) had errors and were skipped.</div>
        )}
        <button onClick={onDone} className="btn-gold w-full">Done</button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        if (!file) { setError("Please choose a CSV file first."); return; }
        importCsv.mutate();
      }}
      className="space-y-4"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Branch</label>
        <select className="input-field w-full" value={branchId} onChange={(e) => setBranchId(e.target.value)} required>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">CSV file</label>
        <div
          onClick={() => fileInput.current?.click()}
          className="border border-dashed border-charcoal-border rounded-lg p-6 text-center cursor-pointer hover:border-gold/40 transition"
        >
          <UploadCloud size={22} className="mx-auto text-neutral-500 mb-2" />
          <div className="text-sm text-neutral-400">{file ? file.name : "Click to choose a .csv file"}</div>
          <input
            ref={fileInput} type="file" accept=".csv" className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <p className="text-xs text-neutral-600 mt-2">
          Expected columns: <code className="text-neutral-400">name, phone</code> (required),
          <code className="text-neutral-400"> email, lead_source_id, lead_status_id</code> (optional).
          Duplicate phone numbers within the branch are skipped automatically.
        </p>
      </div>

      {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}

      <button type="submit" disabled={importCsv.isPending} className="btn-gold w-full disabled:opacity-60">
        {importCsv.isPending ? "Importing…" : "Import Leads"}
      </button>
    </form>
  );
}
