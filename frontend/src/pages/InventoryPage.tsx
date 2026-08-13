import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { AlertTriangle } from "lucide-react";

interface InventoryItem {
  id: string;
  name: string;
  stock_qty: number;
  reorder_level: number;
  unit: string;
  unit_cost: number;
  expiry_date?: string | null;
}

export default function InventoryPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");

  const { data: items, isLoading } = useQuery({
    queryKey: ["inventory", activeBranchId],
    queryFn: async () =>
      (await api.get<InventoryItem[]>("/inventory/items", {
        params: activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {},
      })).data,
  });

  const lowStock = (items ?? []).filter((i) => i.stock_qty <= i.reorder_level);

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

      {lowStock.length > 0 && (
        <div className="card p-4 mb-6 border-amber-800/60 bg-amber-950/20 flex items-center gap-3">
          <AlertTriangle size={18} className="text-amber-400 shrink-0" />
          <div className="text-sm text-amber-200">
            {lowStock.length} item{lowStock.length > 1 ? "s" : ""} at or below reorder level.
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Item</th>
              <th className="px-4 py-3 font-medium">Stock</th>
              <th className="px-4 py-3 font-medium">Reorder Level</th>
              <th className="px-4 py-3 font-medium">Unit Cost</th>
              <th className="px-4 py-3 font-medium">Expiry</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
            {(items ?? []).map((item) => {
              const low = item.stock_qty <= item.reorder_level;
              return (
                <tr key={item.id} className={`border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition ${low ? "bg-red-950/10" : ""}`}>
                  <td className="px-4 py-3 text-neutral-200">{item.name}</td>
                  <td className={`px-4 py-3 ${low ? "text-red-400 font-medium" : "text-neutral-300"}`}>
                    {item.stock_qty} {item.unit}
                  </td>
                  <td className="px-4 py-3 text-neutral-500">{item.reorder_level}</td>
                  <td className="px-4 py-3 text-neutral-400">₹{item.unit_cost}</td>
                  <td className="px-4 py-3 text-neutral-500">
                    {item.expiry_date ? new Date(item.expiry_date).toLocaleDateString("en-IN") : "—"}
                  </td>
                </tr>
              );
            })}
            {!isLoading && (items ?? []).length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">No inventory items found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
