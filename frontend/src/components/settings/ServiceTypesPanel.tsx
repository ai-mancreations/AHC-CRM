import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { Plus } from "lucide-react";

interface ServiceType {
  id: string;
  name: string;
  sac_code: string;
  base_price: number;
  branch_price_overrides: Record<string, number>;
  default_gst_rate: number;
}

export function ServiceTypesPanel() {
  const { branches } = useBranch();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", base_price: "", sac_code: "999599", default_gst_rate: "18" });

  const { data: serviceTypes, isLoading } = useQuery({
    queryKey: ["settings", "service-types"],
    queryFn: async () => (await api.get<ServiceType[]>("/settings/service-types")).data,
  });

  const create = useMutation({
    mutationFn: async () =>
      api.post("/settings/service-types", {
        name: form.name,
        sac_code: form.sac_code,
        base_price: Number(form.base_price),
        default_gst_rate: Number(form.default_gst_rate),
        branch_price_overrides: {},
      }),
    onSuccess: () => {
      setForm({ name: "", base_price: "", sac_code: "999599", default_gst_rate: "18" });
      queryClient.invalidateQueries({ queryKey: ["settings", "service-types"] });
    },
  });

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => { e.preventDefault(); if (form.name && form.base_price) create.mutate(); }}
        className="card p-4 grid grid-cols-2 md:grid-cols-4 gap-3 items-end"
      >
        <div className="col-span-2 md:col-span-1">
          <label className="text-xs text-neutral-400 mb-1 block">Service name</label>
          <input className="input-field w-full" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Base price (₹)</label>
          <input type="number" className="input-field w-full" value={form.base_price} onChange={(e) => setForm((f) => ({ ...f, base_price: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">SAC code</label>
          <input className="input-field w-full" value={form.sac_code} onChange={(e) => setForm((f) => ({ ...f, sac_code: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">GST %</label>
          <input type="number" className="input-field w-full" value={form.default_gst_rate} onChange={(e) => setForm((f) => ({ ...f, default_gst_rate: e.target.value }))} />
        </div>
        <button type="submit" className="btn-gold flex items-center justify-center gap-1 text-sm h-9 col-span-2 md:col-span-4">
          <Plus size={15} /> Add Service Type
        </button>
      </form>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Service</th>
              <th className="px-4 py-3 font-medium">SAC</th>
              <th className="px-4 py-3 font-medium">Base Price</th>
              <th className="px-4 py-3 font-medium">GST %</th>
              {branches.map((b) => <th key={b.id} className="px-4 py-3 font-medium">{b.code} override</th>)}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={4 + branches.length} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
            {(serviceTypes ?? []).map((st) => (
              <tr key={st.id} className="border-b border-charcoal-border/60">
                <td className="px-4 py-3 text-neutral-200">{st.name}</td>
                <td className="px-4 py-3 text-neutral-500">{st.sac_code}</td>
                <td className="px-4 py-3 text-gold-light">₹{st.base_price}</td>
                <td className="px-4 py-3 text-neutral-400">{st.default_gst_rate}%</td>
                {branches.map((b) => (
                  <td key={b.id} className="px-4 py-3 text-neutral-500">
                    {st.branch_price_overrides?.[b.code] ? `₹${st.branch_price_overrides[b.code]}` : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
