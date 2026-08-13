import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function CompleteFollowUpForm({ followUpId, onDone }: { followUpId: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [scheduleNext, setScheduleNext] = useState(false);
  const [nextDate, setNextDate] = useState("");
  const [nextNotes, setNextNotes] = useState("");

  const complete = useMutation({
    mutationFn: async () =>
      api.post(`/follow-ups/${followUpId}/complete`, {
        comment: comment || null,
        reschedule_due_date: scheduleNext && nextDate ? new Date(nextDate).toISOString() : null,
        reschedule_notes: scheduleNext ? nextNotes || null : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
      onDone();
    },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); complete.mutate(); }}
      className="space-y-4"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Comment (optional)</label>
        <textarea
          className="input-field w-full" rows={2} placeholder="How did it go?"
          value={comment} onChange={(e) => setComment(e.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-neutral-300">
        <input type="checkbox" checked={scheduleNext} onChange={(e) => setScheduleNext(e.target.checked)} />
        Schedule next follow-up
      </label>

      {scheduleNext && (
        <div className="space-y-2 pl-1">
          <input
            type="date" className="input-field w-full"
            value={nextDate} onChange={(e) => setNextDate(e.target.value)} required={scheduleNext}
          />
          <textarea
            className="input-field w-full" rows={2} placeholder="Notes for the next follow-up…"
            value={nextNotes} onChange={(e) => setNextNotes(e.target.value)}
          />
        </div>
      )}

      <button type="submit" disabled={complete.isPending} className="btn-gold w-full disabled:opacity-60">
        {complete.isPending ? "Saving…" : "Mark Done"}
      </button>
    </form>
  );
}
