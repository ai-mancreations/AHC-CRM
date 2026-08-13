import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Modal } from "@/components/shared/Modal";
import { CompleteFollowUpForm } from "@/components/leads/CompleteFollowUpForm";
import { CheckCircle, MessageSquarePlus, Phone } from "lucide-react";
import type { Lead } from "@/types";

interface Comment { text: string; created_at: string; user_name?: string; }
interface FollowUp {
  id: string;
  due_date: string;
  notes?: string | null;
  lead_id?: string | null;
  status: string;
  comments: Comment[];
}

const buckets = ["overdue", "today", "upcoming"] as const;

export default function CallsFollowUpsPage() {
  const [bucket, setBucket] = useState<(typeof buckets)[number]>("today");
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [commentingId, setCommentingId] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");
  const queryClient = useQueryClient();

  const { data: followUps, isLoading } = useQuery({
    queryKey: ["follow-ups", bucket],
    queryFn: async () => (await api.get<FollowUp[]>("/follow-ups", { params: { bucket } })).data,
  });

  const { data: leads } = useQuery({
    queryKey: ["leads", "all-for-followups"],
    queryFn: async () => (await api.get<Lead[]>("/leads")).data,
  });

  const leadById = useMemo(() => Object.fromEntries((leads ?? []).map((l) => [l.id, l])), [leads]);

  const addComment = useMutation({
    mutationFn: async ({ id, text }: { id: string; text: string }) =>
      api.post(`/follow-ups/${id}/comments`, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
      setCommentingId(null);
      setCommentText("");
    },
  });

  const bucketCounts: Record<string, number> = {};

  return (
    <div>
      <div className="flex gap-2 mb-6">
        {buckets.map((b) => (
          <button
            key={b}
            onClick={() => setBucket(b)}
            className={`px-4 py-1.5 rounded-full text-sm capitalize transition ${
              bucket === b ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            {b} {b === "overdue" && "⚠️"}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {isLoading && <div className="text-neutral-600">Loading…</div>}
        {(followUps ?? []).map((fu) => {
          const lead = fu.lead_id ? leadById[fu.lead_id] : null;
          return (
            <div key={fu.id} className="card p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  {lead && (
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-neutral-100">{lead.name}</span>
                      <span className="flex items-center gap-1 text-xs text-neutral-500">
                        <Phone size={11} /> {lead.phone}
                      </span>
                    </div>
                  )}
                  <div className="text-sm text-neutral-300">{fu.notes ?? "Follow-up"}</div>
                  <div className="text-xs text-neutral-500 mt-1">
                    Due {new Date(fu.due_date).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                  </div>

                  {fu.comments.length > 0 && (
                    <div className="mt-3 space-y-1.5 border-l-2 border-charcoal-border pl-3">
                      {fu.comments.map((c, i) => (
                        <div key={i} className="text-xs">
                          <span className="text-neutral-400">{c.text}</span>
                          {c.user_name && <span className="text-neutral-600"> — {c.user_name}</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  {commentingId === fu.id && (
                    <div className="mt-3 flex gap-2">
                      <input
                        className="input-field flex-1 text-sm" placeholder="Add a comment…"
                        value={commentText} onChange={(e) => setCommentText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && commentText.trim()) {
                            addComment.mutate({ id: fu.id, text: commentText.trim() });
                          }
                        }}
                        autoFocus
                      />
                      <button
                        onClick={() => commentText.trim() && addComment.mutate({ id: fu.id, text: commentText.trim() })}
                        className="btn-ghost text-xs px-3"
                      >
                        Post
                      </button>
                    </div>
                  )}
                </div>

                <div className="flex flex-col items-end gap-2 shrink-0">
                  <button
                    onClick={() => setCompletingId(fu.id)}
                    className="text-emerald-400 hover:text-emerald-300 transition flex items-center gap-1 text-sm"
                  >
                    <CheckCircle size={16} /> Done
                  </button>
                  <button
                    onClick={() => setCommentingId(commentingId === fu.id ? null : fu.id)}
                    className="text-neutral-500 hover:text-gold-light transition flex items-center gap-1 text-xs"
                  >
                    <MessageSquarePlus size={14} /> Comment
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        {!isLoading && (followUps ?? []).length === 0 && (
          <div className="text-neutral-600 text-sm">No follow-ups in this bucket.</div>
        )}
      </div>

      <Modal open={!!completingId} onClose={() => setCompletingId(null)} title="Complete Follow-Up">
        {completingId && <CompleteFollowUpForm followUpId={completingId} onDone={() => setCompletingId(null)} />}
      </Modal>
    </div>
  );
}
