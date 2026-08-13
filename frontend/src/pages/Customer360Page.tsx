import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Sparkles } from "lucide-react";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const fmtDate = (d: string) => new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
const monthKey = (d: string) => new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

const VISIT_REASON_LABELS: Record<string, string> = {
  NEW_PATCH: "New Patch",
  SERVICE: "Service / Maintenance",
};

interface Technician { id: string; name: string; }
interface ServiceTypeRef { id: string; name: string; }

export default function Customer360Page() {
  const { id } = useParams();

  const { data, isLoading } = useQuery({
    queryKey: ["customer-360", id],
    queryFn: async () => (await api.get(`/customers/${id}/360`)).data,
  });

  const { data: technicians } = useQuery({
    queryKey: ["technicians", "all"],
    queryFn: async () => (await api.get<Technician[]>("/technicians")).data,
  });

  const { data: serviceTypes } = useQuery({
    queryKey: ["settings", "service-types"],
    queryFn: async () => (await api.get<ServiceTypeRef[]>("/settings/service-types")).data,
  });

  const techById = useMemo(() => Object.fromEntries((technicians ?? []).map((t) => [t.id, t.name])), [technicians]);
  const serviceTypeById = useMemo(() => Object.fromEntries((serviceTypes ?? []).map((s) => [s.id, s.name])), [serviceTypes]);

  const history = useMemo(() => {
    if (!data) return [];
    return [...data.services]
      .sort((a: any, b: any) => new Date(a.performed_at).getTime() - new Date(b.performed_at).getTime())
      .map((s: any) => ({
        id: s.id,
        date: s.performed_at,
        serviceType: serviceTypeById[s.service_type_id] ?? "—",
        technician: techById[s.technician_id] ?? "—",
        visitReason: VISIT_REASON_LABELS[s.visit_reason] ?? s.visit_reason,
        price: s.price_charged,
      }));
  }, [data, techById, serviceTypeById]);

  const historyByMonth = useMemo(() => {
    const groups: Record<string, typeof history> = {};
    for (const row of history) {
      const key = monthKey(row.date);
      if (!groups[key]) groups[key] = [];
      groups[key].push(row);
    }
    return groups;
  }, [history]);

  const firstVisit = history[0];

  if (isLoading) return <div className="text-neutral-500">Loading…</div>;
  if (!data) return null;

  const { customer, installations, invoices, payments } = data;

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <h2 className="font-display text-2xl text-gold-light">{customer.name}</h2>
        <p className="text-neutral-400 text-sm mt-1">{customer.phone} {customer.email && `· ${customer.email}`}</p>
        {customer.address && <p className="text-neutral-500 text-sm mt-1">{customer.address}</p>}
      </div>

      {firstVisit && (
        <div className="card p-5 border-gold/30 bg-gold/5">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={16} className="text-gold-light" />
            <h3 className="text-sm font-medium text-gold-light">First Visit</h3>
          </div>
          <p className="text-sm text-neutral-300">
            {fmtDate(firstVisit.date)} — <span className="text-neutral-200">{firstVisit.visitReason}</span>
            {" "}({firstVisit.serviceType}) attended by <span className="text-neutral-200">{firstVisit.technician}</span>
          </p>
        </div>
      )}

      <div className="card p-5">
        <h3 className="font-display text-lg text-neutral-200 mb-4">Full Service History ({history.length})</h3>
        {history.length === 0 && <div className="text-neutral-600 text-sm">No services yet.</div>}

        <div className="space-y-6">
          {Object.entries(historyByMonth).map(([month, rows]) => (
            <div key={month}>
              <div className="text-xs uppercase tracking-wide text-neutral-500 mb-2">{month}</div>
              <div className="overflow-hidden rounded-lg border border-charcoal-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-neutral-500 bg-charcoal-700/40">
                      <th className="px-4 py-2 font-medium">Date</th>
                      <th className="px-4 py-2 font-medium">Visit Type</th>
                      <th className="px-4 py-2 font-medium">Service</th>
                      <th className="px-4 py-2 font-medium">Performed By</th>
                      <th className="px-4 py-2 font-medium text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id} className="border-t border-charcoal-border/60">
                        <td className="px-4 py-2.5 text-neutral-400">{fmtDate(row.date)}</td>
                        <td className="px-4 py-2.5 text-neutral-300">{row.visitReason}</td>
                        <td className="px-4 py-2.5 text-neutral-300">{row.serviceType}</td>
                        <td className="px-4 py-2.5 text-gold-light">{row.technician}</td>
                        <td className="px-4 py-2.5 text-neutral-300 text-right">{inr(row.price)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-5">
          <h3 className="font-display text-lg text-neutral-200 mb-3">Hair Systems ({installations.length})</h3>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {installations.map((i: any) => (
              <div key={i.id} className="text-sm border-b border-charcoal-border/50 pb-2">
                <div className="text-neutral-300">Installed {fmtDate(i.installed_at)}</div>
                <div className="text-neutral-500 text-xs">By {techById[i.technician_id] ?? "—"}</div>
                {i.next_maintenance_due && (
                  <div className="text-neutral-500 text-xs">Next maintenance: {fmtDate(i.next_maintenance_due)}</div>
                )}
              </div>
            ))}
            {installations.length === 0 && <div className="text-neutral-600 text-sm">No installations yet.</div>}
          </div>
        </div>

        <div className="card p-5">
          <h3 className="font-display text-lg text-neutral-200 mb-3">Invoices ({invoices.length})</h3>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {invoices.map((inv: any) => (
              <div key={inv.id} className="flex justify-between text-sm border-b border-charcoal-border/50 pb-2">
                <span className="text-neutral-400">{inv.invoice_number}</span>
                <span className="text-gold-light">{inr(inv.grand_total)}</span>
                <span className="text-xs text-neutral-500">{inv.status}</span>
              </div>
            ))}
            {invoices.length === 0 && <div className="text-neutral-600 text-sm">No invoices yet.</div>}
          </div>
        </div>

        <div className="card p-5">
          <h3 className="font-display text-lg text-neutral-200 mb-3">Payments ({payments.length})</h3>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {payments.map((p: any) => (
              <div key={p.id} className="flex justify-between text-sm border-b border-charcoal-border/50 pb-2">
                <span className="text-neutral-400">{fmtDate(p.paid_at)}</span>
                <span className="text-gold-light">{inr(p.amount)}</span>
                <span className="text-xs text-neutral-500">{p.method}</span>
              </div>
            ))}
            {payments.length === 0 && <div className="text-neutral-600 text-sm">No payments yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
