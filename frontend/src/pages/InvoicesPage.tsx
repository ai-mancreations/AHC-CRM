import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import type { Invoice } from "@/types";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const statusColors: Record<string, string> = {
  PAID: "text-emerald-400 bg-emerald-950/40",
  PARTIALLY_PAID: "text-amber-400 bg-amber-950/40",
  OVERDUE: "text-red-400 bg-red-950/40",
  DRAFT: "text-neutral-400 bg-neutral-800/60",
  CANCELLED: "text-neutral-500 bg-neutral-900/60",
};

export default function InvoicesPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");

  const { data: invoices, isLoading } = useQuery({
    queryKey: ["invoices", activeBranchId],
    queryFn: async () =>
      (await api.get<Invoice[]>("/invoices", {
        params: activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {},
      })).data,
  });

  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? id;
  const totalOutstanding = (invoices ?? []).reduce((sum, i) => sum + (i.grand_total - i.amount_paid), 0);

  return (
    <div>
      <div className="flex gap-2 flex-wrap mb-4">
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

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="card p-4">
          <div className="text-xs text-neutral-500">Total Invoices</div>
          <div className="kpi-value">{invoices?.length ?? 0}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-neutral-500">Outstanding Balance</div>
          <div className="kpi-value">{inr(totalOutstanding)}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-neutral-500">Total Revenue (shown)</div>
          <div className="kpi-value">{inr((invoices ?? []).reduce((s, i) => s + i.grand_total, 0))}</div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Invoice #</th>
              <th className="px-4 py-3 font-medium">Branch</th>
              <th className="px-4 py-3 font-medium">FY</th>
              <th className="px-4 py-3 font-medium">Issued</th>
              <th className="px-4 py-3 font-medium">Total</th>
              <th className="px-4 py-3 font-medium">Balance</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
            {(invoices ?? []).map((inv) => (
              <tr key={inv.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                <td className="px-4 py-3 text-gold-light">{inv.invoice_number}</td>
                <td className="px-4 py-3 text-neutral-400">{branchName(inv.branch_id)}</td>
                <td className="px-4 py-3 text-neutral-500">{inv.financial_year}</td>
                <td className="px-4 py-3 text-neutral-400">{new Date(inv.issued_at).toLocaleDateString("en-IN")}</td>
                <td className="px-4 py-3">{inr(inv.grand_total)}</td>
                <td className="px-4 py-3 text-neutral-400">{inr(inv.grand_total - inv.amount_paid)}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-1 rounded-full ${statusColors[inv.status] ?? ""}`}>
                    {inv.status.replaceAll("_", " ")}
                  </span>
                </td>
              </tr>
            ))}
            {!isLoading && (invoices ?? []).length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-neutral-600">No invoices found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
