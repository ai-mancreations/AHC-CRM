import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Branch, SettingsItem } from "@/types";

const VISIT_REASONS = [
  { value: "NEW_PATCH", label: "New Patch" },
  { value: "SERVICE", label: "Service / Maintenance" },
];

export function AddLeadForm({
  branches, sources, statuses, defaultBranchId, onDone,
}: {
  branches: Branch[];
  sources: SettingsItem[];
  statuses: SettingsItem[];
  defaultBranchId?: string | null;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    branch_id: defaultBranchId ?? branches[0]?.id ?? "",
    name: "",
    phone: "",
    email: "",
    lead_source_id: sources[0]?.id ?? "",
    lead_status_id: statuses[0]?.id ?? "",
    visit_reason: "NEW_PATCH",
    notes: "",
    follow_up_date: "",
    follow_up_notes: "",
  });
  const [error, setError] = useState<string | null>(null);

  const createLead = useMutation({
    mutationFn: async () => {
      const { follow_up_date, follow_up_notes, ...leadBody } = form;
      const { data: lead } = await api.post("/leads", leadBody);
      if (follow_up_date) {
        await api.post("/follow-ups", {
          lead_id: lead.id,
          branch_id: form.branch_id,
          due_date: new Date(follow_up_date).toISOString(),
          notes: follow_up_notes || null,
        });
      }
      return lead;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
      onDone();
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? "Could not create lead"),
  });

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        createLead.mutate();
      }}
      className="space-y-3"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Branch</label>
        <select className="input-field w-full" value={form.branch_id} onChange={(e) => set("branch_id", e.target.value)} required>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Name</label>
          <input className="input-field w-full" value={form.name} onChange={(e) => set("name", e.target.value)} required />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Phone</label>
          <input className="input-field w-full" value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+91XXXXXXXXXX" required />
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Email (optional)</label>
        <input type="email" className="input-field w-full" value={form.email} onChange={(e) => set("email", e.target.value)} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Lead Source</label>
          <select className="input-field w-full" value={form.lead_source_id} onChange={(e) => set("lead_source_id", e.target.value)} required>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Status</label>
          <select className="input-field w-full" value={form.lead_status_id} onChange={(e) => set("lead_status_id", e.target.value)} required>
            {statuses.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Visit Reason</label>
        <select className="input-field w-full" value={form.visit_reason} onChange={(e) => set("visit_reason", e.target.value)}>
          {VISIT_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Notes (optional)</label>
        <textarea className="input-field w-full" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
      </div>

      <div className="border-t border-charcoal-border pt-3">
        <label className="text-xs text-neutral-400 mb-1 block">Schedule a follow-up (optional)</label>
        <input
          type="date" className="input-field w-full mb-2"
          value={form.follow_up_date} onChange={(e) => set("follow_up_date", e.target.value)}
        />
        {form.follow_up_date && (
          <textarea
            className="input-field w-full" rows={2} placeholder="What to follow up about…"
            value={form.follow_up_notes} onChange={(e) => set("follow_up_notes", e.target.value)}
          />
        )}
      </div>

      {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}

      <button type="submit" disabled={createLead.isPending} className="btn-gold w-full disabled:opacity-60">
        {createLead.isPending ? "Adding…" : "Add Lead"}
      </button>
    </form>
  );
}
