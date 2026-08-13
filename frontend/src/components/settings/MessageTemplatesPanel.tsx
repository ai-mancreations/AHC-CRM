import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus } from "lucide-react";

interface MessageTemplate {
  id: string;
  channel: string;
  name: string;
  subject?: string | null;
  body: string;
  trigger_event?: string | null;
}

const CHANNELS = ["WHATSAPP", "SMS", "EMAIL"];

export function MessageTemplatesPanel() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ channel: "WHATSAPP", name: "", subject: "", body: "", trigger_event: "" });

  const { data: templates, isLoading } = useQuery({
    queryKey: ["settings", "message-templates"],
    queryFn: async () => (await api.get<MessageTemplate[]>("/settings/message-templates")).data,
  });

  const create = useMutation({
    mutationFn: async () =>
      api.post("/settings/message-templates", {
        channel: form.channel, name: form.name, subject: form.subject || null,
        body: form.body, trigger_event: form.trigger_event || null, placeholders: [],
      }),
    onSuccess: () => {
      setForm({ channel: "WHATSAPP", name: "", subject: "", body: "", trigger_event: "" });
      queryClient.invalidateQueries({ queryKey: ["settings", "message-templates"] });
    },
  });

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => { e.preventDefault(); if (form.name && form.body) create.mutate(); }}
        className="card p-4 space-y-3"
      >
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-neutral-400 mb-1 block">Channel</label>
            <select className="input-field w-full" value={form.channel} onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value }))}>
              {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-neutral-400 mb-1 block">Name</label>
            <input className="input-field w-full" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs text-neutral-400 mb-1 block">Trigger event (optional)</label>
            <input className="input-field w-full" placeholder="e.g. NEW_LEAD" value={form.trigger_event} onChange={(e) => setForm((f) => ({ ...f, trigger_event: e.target.value }))} />
          </div>
        </div>
        {form.channel === "EMAIL" && (
          <div>
            <label className="text-xs text-neutral-400 mb-1 block">Subject</label>
            <input className="input-field w-full" value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} />
          </div>
        )}
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Body (use {"{{placeholder}}"} for variables)</label>
          <textarea className="input-field w-full" rows={3} value={form.body} onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))} />
        </div>
        <button type="submit" className="btn-gold flex items-center justify-center gap-1 text-sm h-9 w-full">
          <Plus size={15} /> Add Template
        </button>
      </form>

      <div className="card divide-y divide-charcoal-border">
        {isLoading && <div className="p-4 text-neutral-600 text-sm">Loading…</div>}
        {(templates ?? []).map((t) => (
          <div key={t.id} className="px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-wide text-gold-light/80 bg-gold/10 px-2 py-0.5 rounded-full">{t.channel}</span>
              <span className="text-sm text-neutral-200">{t.name}</span>
              {t.trigger_event && <span className="text-xs text-neutral-600 ml-auto">{t.trigger_event}</span>}
            </div>
            <p className="text-xs text-neutral-500 mt-1">{t.body}</p>
          </div>
        ))}
        {!isLoading && (templates ?? []).length === 0 && <div className="p-4 text-neutral-600 text-sm">No templates yet.</div>}
      </div>
    </div>
  );
}
