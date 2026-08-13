import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SettingsItem } from "@/types";
import { Phone, MessageSquarePlus, UserCheck, Clock } from "lucide-react";

interface LeadFull {
  id: string;
  branch_id: string;
  name: string;
  phone: string;
  email?: string | null;
  lead_source_id: string;
  lead_status_id: string;
  visit_reason: string;
  notes?: string | null;
  converted_customer_id?: string | null;
}

interface Activity {
  id: string;
  activity_type: string;
  description: string;
  created_at: string;
}

interface FollowUp {
  id: string;
  due_date: string;
  notes?: string | null;
  status: string;
}

const ACTIVITY_LABELS: Record<string, string> = {
  SYSTEM: "System", CALL: "Call", STATUS_CHANGE: "Status Change", NOTE: "Note", WHATSAPP: "WhatsApp",
};

export function LeadDetailModal({ leadId, statuses, onClose }: {
  leadId: string;
  statuses: SettingsItem[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [followUpDate, setFollowUpDate] = useState("");
  const [followUpNotes, setFollowUpNotes] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["lead-detail", leadId],
    queryFn: async () => (await api.get<{ lead: LeadFull; activities: Activity[] }>(`/leads/${leadId}`)).data,
  });

  const { data: followUps } = useQuery({
    queryKey: ["follow-ups", "for-lead", leadId],
    queryFn: async () => (await api.get<FollowUp[]>("/follow-ups", { params: { lead_id: leadId } })).data,
  });

  const addComment = useMutation({
    mutationFn: async (text: string) => api.post(`/leads/${leadId}/notes`, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lead-detail", leadId] });
      setComment("");
    },
  });

  const addFollowUp = useMutation({
    mutationFn: async () =>
      api.post("/follow-ups", {
        lead_id: leadId,
        branch_id: data!.lead.branch_id,
        due_date: new Date(followUpDate).toISOString(),
        notes: followUpNotes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups", "for-lead", leadId] });
      setFollowUpDate("");
      setFollowUpNotes("");
    },
  });

  const convertToCustomer = useMutation({
    mutationFn: async () => api.post(`/leads/${leadId}/convert`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lead-detail", leadId] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  if (isLoading || !data) return <div className="text-neutral-500 text-sm">Loading…</div>;
  const { lead, activities } = data;
  const status = statuses.find((s) => s.id === lead.lead_status_id);

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-lg text-neutral-100 font-medium">{lead.name}</h3>
          {status && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${status.extra?.color ?? "#C9A227"}22`, color: status.extra?.color ?? "#C9A227" }}>
              {status.name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-sm text-neutral-400 mt-1">
          <Phone size={13} /> {lead.phone} {lead.email && `· ${lead.email}`}
        </div>
        {lead.notes && <p className="text-sm text-neutral-400 mt-2">{lead.notes}</p>}
      </div>

      {lead.converted_customer_id ? (
        <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-3 py-2">
          <UserCheck size={15} /> Converted to customer
        </div>
      ) : (
        <button
          onClick={() => convertToCustomer.mutate()}
          disabled={convertToCustomer.isPending}
          className="btn-gold w-full text-sm disabled:opacity-60"
        >
          {convertToCustomer.isPending ? "Converting…" : "Convert to Customer"}
        </button>
      )}

      <div>
        <h4 className="text-sm font-medium text-neutral-300 mb-2 flex items-center gap-2">
          <Clock size={14} /> Follow-Ups
        </h4>
        <div className="space-y-2 mb-3">
          {(followUps ?? []).map((fu) => (
            <div key={fu.id} className="bg-charcoal-700 rounded-lg px-3 py-2 text-xs">
              <div className="flex justify-between">
                <span className="text-neutral-300">{fu.notes ?? "Follow-up"}</span>
                <span className={fu.status === "PENDING" ? "text-amber-400" : "text-neutral-500"}>{fu.status}</span>
              </div>
              <div className="text-neutral-500 mt-1">{new Date(fu.due_date).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</div>
            </div>
          ))}
          {(followUps ?? []).length === 0 && <div className="text-xs text-neutral-600">No follow-ups scheduled yet.</div>}
        </div>
        <div className="flex gap-2">
          <input type="date" className="input-field text-sm" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)} />
          <input
            className="input-field flex-1 text-sm" placeholder="Follow-up notes…"
            value={followUpNotes} onChange={(e) => setFollowUpNotes(e.target.value)}
          />
          <button
            onClick={() => followUpDate && addFollowUp.mutate()}
            disabled={!followUpDate || addFollowUp.isPending}
            className="btn-ghost text-xs px-3 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      <div>
        <h4 className="text-sm font-medium text-neutral-300 mb-2 flex items-center gap-2">
          <MessageSquarePlus size={14} /> Timeline &amp; Comments
        </h4>
        <div className="flex gap-2 mb-3">
          <input
            className="input-field flex-1 text-sm" placeholder="Add a comment…"
            value={comment} onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && comment.trim()) addComment.mutate(comment.trim()); }}
          />
          <button
            onClick={() => comment.trim() && addComment.mutate(comment.trim())}
            className="btn-ghost text-xs px-3"
          >
            Post
          </button>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto border-l-2 border-charcoal-border pl-3">
          {activities.map((a) => (
            <div key={a.id} className="text-xs">
              <span className="text-neutral-500">[{ACTIVITY_LABELS[a.activity_type] ?? a.activity_type}]</span>{" "}
              <span className="text-neutral-300">{a.description}</span>
              <div className="text-neutral-600">{new Date(a.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}</div>
            </div>
          ))}
          {activities.length === 0 && <div className="text-xs text-neutral-600">No activity yet.</div>}
        </div>
      </div>
    </div>
  );
}
