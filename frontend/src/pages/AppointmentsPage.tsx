import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { Modal } from "@/components/shared/Modal";
import { BookAppointmentForm } from "@/components/appointments/BookAppointmentForm";
import { Plus } from "lucide-react";

interface Appointment {
  id: string;
  cabin_id: string;
  start_time: string;
  end_time: string;
  status: string;
  visit_reason: string;
}

interface Cabin { id: string; name: string; }

const STATUS_COLORS: Record<string, string> = {
  BOOKED: "text-neutral-300 bg-charcoal-700",
  CONFIRMED: "text-blue-300 bg-blue-950/40",
  IN_PROGRESS: "text-amber-300 bg-amber-950/40",
  COMPLETED: "text-emerald-300 bg-emerald-950/40",
  NO_SHOW: "text-red-300 bg-red-950/40",
  CANCELLED: "text-neutral-500 bg-neutral-900/60",
};

export default function AppointmentsPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [showBookModal, setShowBookModal] = useState(false);

  const branchId = activeBranchId ?? branches[0]?.id ?? null;
  const activeBranch = branches.find((b) => b.id === branchId);

  const { data: cabins } = useQuery({
    queryKey: ["cabins", branchId],
    queryFn: async () => (await api.get<Cabin[]>("/branches/cabins", { params: { branch_id: branchId } })).data,
    enabled: !!branchId,
  });

  const dayStart = new Date(`${date}T00:00:00`);
  const dayEnd = new Date(`${date}T23:59:59`);

  const { data: appointments } = useQuery({
    queryKey: ["appointments", branchId, date],
    queryFn: async () =>
      (await api.get<Appointment[]>("/appointments", {
        params: { branch_id: branchId, date_from: dayStart.toISOString(), date_to: dayEnd.toISOString() },
      })).data,
    enabled: !!branchId,
  });

  if (branches.length === 0) {
    return <div className="text-neutral-500 text-sm">Loading branches…</div>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex gap-2">
          {branches.map((b) => (
            <button
              key={b.id}
              onClick={() => setActiveBranchId(b.id)}
              className={`px-4 py-1.5 rounded-full text-sm transition ${
                branchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
              }`}
            >
              {b.name}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <input type="date" className="input-field" value={date} onChange={(e) => setDate(e.target.value)} />
          <button onClick={() => setShowBookModal(true)} className="btn-gold flex items-center gap-2 text-sm">
            <Plus size={16} /> Book Slot
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(cabins ?? []).map((cabin) => {
          const cabinAppts = (appointments ?? [])
            .filter((a) => a.cabin_id === cabin.id)
            .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
          return (
            <div key={cabin.id} className="card p-4">
              <h3 className="font-display text-lg text-gold-light mb-3">{cabin.name}</h3>
              <div className="space-y-2">
                {cabinAppts.length === 0 && <div className="text-xs text-neutral-600">No bookings for this day.</div>}
                {cabinAppts.map((a) => (
                  <div key={a.id} className="bg-charcoal-700 rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-neutral-200">
                        {new Date(a.start_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                        {" – "}
                        {new Date(a.end_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full ${STATUS_COLORS[a.status] ?? ""}`}>{a.status}</span>
                    </div>
                    <div className="text-neutral-500 mt-1">
                      {a.visit_reason === "NEW_PATCH" ? "New Patch" : "Service / Maintenance"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        {(cabins ?? []).length === 0 && (
          <div className="text-neutral-600 text-sm col-span-full">No cabins configured for this branch yet.</div>
        )}
      </div>

      <Modal open={showBookModal} onClose={() => setShowBookModal(false)} title={`Book Slot — ${activeBranch?.name ?? ""}`}>
        {activeBranch && <BookAppointmentForm branch={activeBranch} onDone={() => setShowBookModal(false)} />}
      </Modal>
    </div>
  );
}
