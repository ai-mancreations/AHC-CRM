import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Branch, Customer } from "@/types";

interface Cabin { id: string; name: string; }
interface Technician { id: string; name: string; }

const VISIT_REASONS = [
  { value: "NEW_PATCH", label: "New Patch" },
  { value: "SERVICE", label: "Service / Maintenance" },
];

const DURATIONS = [
  { minutes: 60, label: "1 hour" },
  { minutes: 90, label: "1.5 hours" },
  { minutes: 120, label: "2 hours" },
];

export function BookAppointmentForm({ branch, onDone }: { branch: Branch; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    cabin_id: "",
    customer_id: "",
    technician_id: "",
    visit_reason: "NEW_PATCH",
    date: new Date().toISOString().slice(0, 10),
    time: "10:00",
    duration: 90,
    notes: "",
  });
  const [customerSearch, setCustomerSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: cabins } = useQuery({
    queryKey: ["cabins", branch.id],
    queryFn: async () => (await api.get<Cabin[]>("/branches/cabins", { params: { branch_id: branch.id } })).data,
  });

  const { data: technicians } = useQuery({
    queryKey: ["technicians", branch.id],
    queryFn: async () => (await api.get<Technician[]>("/technicians", { params: { branch_id: branch.id } })).data,
  });

  const { data: customers } = useQuery({
    queryKey: ["customers", branch.id, customerSearch],
    queryFn: async () =>
      (await api.get<Customer[]>("/customers", {
        params: { branch_id: branch.id, ...(customerSearch ? { search: customerSearch } : {}) },
      })).data,
  });

  const createAppointment = useMutation({
    mutationFn: async () => {
      const start = new Date(`${form.date}T${form.time}:00`);
      const end = new Date(start.getTime() + form.duration * 60000);
      return api.post("/appointments", {
        branch_id: branch.id,
        cabin_id: form.cabin_id,
        customer_id: form.customer_id || null,
        technician_id: form.technician_id || null,
        visit_reason: form.visit_reason,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: form.notes || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      onDone();
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? "Could not create booking"),
  });

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        if (!form.cabin_id) { setError("Please select a cabin."); return; }
        createAppointment.mutate();
      }}
      className="space-y-3"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Cabin</label>
        <select className="input-field w-full" value={form.cabin_id} onChange={(e) => set("cabin_id", e.target.value)} required>
          <option value="">Select cabin…</option>
          {(cabins ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Date</label>
          <input type="date" className="input-field w-full" value={form.date} onChange={(e) => set("date", e.target.value)} required />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Start Time</label>
          <input type="time" className="input-field w-full" value={form.time} onChange={(e) => set("time", e.target.value)} required />
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Duration</label>
        <select className="input-field w-full" value={form.duration} onChange={(e) => set("duration", Number(e.target.value))}>
          {DURATIONS.map((d) => <option key={d.minutes} value={d.minutes}>{d.label}</option>)}
        </select>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Customer (optional — search by name/phone)</label>
        <input
          className="input-field w-full mb-1" placeholder="Search customer…"
          value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)}
        />
        <select className="input-field w-full" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)}>
          <option value="">No customer linked</option>
          {(customers ?? []).map((c) => <option key={c.id} value={c.id}>{c.name} — {c.phone}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Technician</label>
          <select className="input-field w-full" value={form.technician_id} onChange={(e) => set("technician_id", e.target.value)}>
            <option value="">Unassigned</option>
            {(technicians ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Visit Reason</label>
          <select className="input-field w-full" value={form.visit_reason} onChange={(e) => set("visit_reason", e.target.value)}>
            {VISIT_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Notes (optional)</label>
        <textarea className="input-field w-full" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
      </div>

      {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}

      <button type="submit" disabled={createAppointment.isPending} className="btn-gold w-full disabled:opacity-60">
        {createAppointment.isPending ? "Booking…" : "Book Slot"}
      </button>
    </form>
  );
}
