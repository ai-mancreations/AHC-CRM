import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface CompanyConfig {
  company_name: string;
  fy_start_month: number;
  default_cgst_rate: number;
  default_sgst_rate: number;
  default_igst_rate: number;
}

export function CompanyConfigPanel() {
  const queryClient = useQueryClient();
  const { data: config } = useQuery({
    queryKey: ["settings", "company-config"],
    queryFn: async () => (await api.get<CompanyConfig>("/settings/company-config")).data,
  });

  const [form, setForm] = useState<CompanyConfig | null>(null);
  useEffect(() => { if (config) setForm(config); }, [config]);

  const save = useMutation({
    mutationFn: async () => api.put("/settings/company-config", form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "company-config"] }),
  });

  if (!form) return <div className="text-neutral-600 text-sm">Loading…</div>;

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); save.mutate(); }}
      className="card p-5 space-y-4 max-w-xl"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Company Name</label>
        <input className="input-field w-full" value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
      </div>
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Financial Year Start Month (1-12, India default = 4 for April)</label>
        <input type="number" min={1} max={12} className="input-field w-full" value={form.fy_start_month} onChange={(e) => setForm({ ...form, fy_start_month: Number(e.target.value) })} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Default CGST %</label>
          <input type="number" step="0.1" className="input-field w-full" value={form.default_cgst_rate} onChange={(e) => setForm({ ...form, default_cgst_rate: Number(e.target.value) })} />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Default SGST %</label>
          <input type="number" step="0.1" className="input-field w-full" value={form.default_sgst_rate} onChange={(e) => setForm({ ...form, default_sgst_rate: Number(e.target.value) })} />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Default IGST %</label>
          <input type="number" step="0.1" className="input-field w-full" value={form.default_igst_rate} onChange={(e) => setForm({ ...form, default_igst_rate: Number(e.target.value) })} />
        </div>
      </div>
      <button type="submit" disabled={save.isPending} className="btn-gold disabled:opacity-60">
        {save.isPending ? "Saving…" : "Save Changes"}
      </button>
      {save.isSuccess && <span className="text-emerald-400 text-sm ml-3">Saved.</span>}
    </form>
  );
}
