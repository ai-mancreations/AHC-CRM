import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ProfitTrendChart } from "@/components/dashboard/ProfitTrendChart";
import { IndianRupee, Users, Footprints, CheckCircle2, Phone, Clock } from "lucide-react";
import type { Lead } from "@/types";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

interface FollowUp {
  id: string;
  due_date: string;
  notes?: string | null;
  lead_id?: string | null;
  customer_id?: string | null;
}

function isToday(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

export default function TodayDashboardPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");

  const { data: today, isLoading } = useQuery({
    queryKey: ["dashboard", "today"],
    queryFn: async () => (await api.get("/dashboard/today")).data,
  });

  const { data: ops } = useQuery({
    queryKey: ["dashboard", "daily-operations"],
    queryFn: async () => (await api.get("/dashboard/daily-operations")).data,
  });

  const { data: allLeads } = useQuery({
    queryKey: ["leads", activeBranchId, "today-view"],
    queryFn: async () =>
      (await api.get<Lead[]>("/leads", { params: activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {} })).data,
  });

  const { data: followUps } = useQuery({
    queryKey: ["follow-ups", activeBranchId, "today-view"],
    queryFn: async () =>
      (await api.get<FollowUp[]>("/follow-ups", {
        params: { bucket: "today", ...(activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {}) },
      })).data,
  });

  const todaysLeads = useMemo(() => (allLeads ?? []).filter((l) => isToday(l.created_at)), [allLeads]);

  const branchRows = branches.map((b) => {
    const rev = (today?.revenue_by_branch ?? []).find((r: any) => r._id === b.id);
    const leads = (today?.leads_by_branch ?? []).find((r: any) => r._id === b.id);
    const walkins = (today?.walkins_by_branch ?? []).find((r: any) => r._id === b.id);
    return {
      id: b.id, name: b.name,
      revenue: rev?.revenue ?? 0, invoiceCount: rev?.invoice_count ?? 0,
      leads: leads?.count ?? 0, walkins: walkins?.count ?? 0,
    };
  });

  const selectedRow = activeBranchId !== "ALL" ? branchRows.find((r) => r.id === activeBranchId) : null;

  return (
    <div className="space-y-8">
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveBranchId("ALL")}
          className={`px-4 py-1.5 rounded-full text-sm transition ${
            activeBranchId === "ALL" ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
          }`}
        >
          All Branches
        </button>
        {branches.map((b) => (
          <button
            key={b.id}
            onClick={() => setActiveBranchId(b.id)}
            className={`px-4 py-1.5 rounded-full text-sm transition ${
              activeBranchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      <section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Revenue Today"
            value={isLoading ? "…" : inr(selectedRow ? selectedRow.revenue : today?.total_revenue_today ?? 0)}
            icon={<IndianRupee size={18} />}
          />
          <KpiCard
            label="Leads Today"
            value={isLoading ? "…" : String(selectedRow ? selectedRow.leads : today?.leads_today ?? 0)}
            icon={<Users size={18} />}
          />
          <KpiCard
            label="Walk-Ins Today"
            value={isLoading ? "…" : String(selectedRow ? selectedRow.walkins : today?.walk_ins_today ?? 0)}
            icon={<Footprints size={18} />}
          />
          <KpiCard
            label="Conversions Today"
            value={isLoading ? "…" : String(today?.conversions_today ?? 0)}
            icon={<CheckCircle2 size={18} />}
          />
        </div>
      </section>

      {activeBranchId === "ALL" && branches.length > 0 && (
        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3">Today — By Branch</h2>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
                  <th className="px-4 py-3 font-medium">Branch</th>
                  <th className="px-4 py-3 font-medium">Revenue</th>
                  <th className="px-4 py-3 font-medium">Invoices</th>
                  <th className="px-4 py-3 font-medium">New Leads</th>
                  <th className="px-4 py-3 font-medium">Walk-Ins</th>
                </tr>
              </thead>
              <tbody>
                {branchRows.map((row) => (
                  <tr key={row.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                    <td className="px-4 py-3 text-neutral-200">{row.name}</td>
                    <td className="px-4 py-3 text-gold-light">{inr(row.revenue)}</td>
                    <td className="px-4 py-3 text-neutral-400">{row.invoiceCount}</td>
                    <td className="px-4 py-3 text-neutral-400">{row.leads}</td>
                    <td className="px-4 py-3 text-neutral-400">{row.walkins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3 flex items-center gap-2">
            <Users size={16} className="text-gold-light" /> Today's Leads ({todaysLeads.length})
          </h2>
          <div className="card divide-y divide-charcoal-border max-h-96 overflow-y-auto">
            {todaysLeads.length === 0 && <div className="p-4 text-neutral-600 text-sm">No leads created today yet.</div>}
            {todaysLeads.map((l) => (
              <div key={l.id} className="px-4 py-3">
                <div className="text-sm text-neutral-200">{l.name}</div>
                <div className="flex items-center gap-1.5 text-xs text-neutral-500 mt-1">
                  <Phone size={11} /> {l.phone}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3 flex items-center gap-2">
            <Clock size={16} className="text-gold-light" /> Today's Follow-Ups ({(followUps ?? []).length})
          </h2>
          <div className="card divide-y divide-charcoal-border max-h-96 overflow-y-auto">
            {(followUps ?? []).length === 0 && <div className="p-4 text-neutral-600 text-sm">No follow-ups due today.</div>}
            {(followUps ?? []).map((fu) => (
              <div key={fu.id} className="px-4 py-3">
                <div className="text-sm text-neutral-200">{fu.notes ?? "Follow-up"}</div>
                <div className="text-xs text-neutral-500 mt-1">
                  Due {new Date(fu.due_date).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section>
        <h2 className="font-display text-lg text-neutral-200 mb-3">12-Month Profit Trend</h2>
        <div className="card p-6">
          <ProfitTrendChart branchId={activeBranchId !== "ALL" ? activeBranchId : undefined} />
        </div>
      </section>

      {ops && activeBranchId === "ALL" && (
        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3">Daily Operations (All Branches)</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Object.entries(ops).map(([key, value]) => (
              <div key={key} className="card p-4">
                <div className="text-xs text-neutral-500 capitalize">{key.replaceAll("_", " ")}</div>
                <div className="text-xl text-gold-light font-display mt-1">{String(value)}</div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
