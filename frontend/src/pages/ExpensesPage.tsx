import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

interface Expense {
  id: string;
  description: string;
  amount: number;
  incurred_at: string;
  category_id: string;
}

export default function ExpensesPage() {
  const { selectedBranchId } = useBranch();
  const { data: expenses, isLoading } = useQuery({
    queryKey: ["expenses", selectedBranchId],
    queryFn: async () =>
      (await api.get<Expense[]>("/expenses", { params: selectedBranchId ? { branch_id: selectedBranchId } : {} })).data,
  });

  const total = (expenses ?? []).reduce((s, e) => s + e.amount, 0);

  return (
    <div>
      <div className="card p-4 mb-6 max-w-xs">
        <div className="text-xs text-neutral-500">Total Expenses (shown)</div>
        <div className="kpi-value">{inr(total)}</div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Description</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Date</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={3} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
            {(expenses ?? []).slice(0, 200).map((e) => (
              <tr key={e.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                <td className="px-4 py-3 text-neutral-200">{e.description}</td>
                <td className="px-4 py-3 text-gold-light">{inr(e.amount)}</td>
                <td className="px-4 py-3 text-neutral-500">{new Date(e.incurred_at).toLocaleDateString("en-IN")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
