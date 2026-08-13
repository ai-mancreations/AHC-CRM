import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import type { Customer } from "@/types";
import { Search } from "lucide-react";

export default function CustomersPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");
  const [search, setSearch] = useState("");

  const { data: customers, isLoading } = useQuery({
    queryKey: ["customers", activeBranchId, search],
    queryFn: async () =>
      (await api.get<Customer[]>("/customers", {
        params: { ...(activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {}), ...(search ? { search } : {}) },
      })).data,
  });

  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? id;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
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

        <div className="relative max-w-xs w-full">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            className="input-field w-full pl-9"
            placeholder="Search by name or phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Branch</th>
              <th className="px-4 py-3 font-medium">Phone</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>
            )}
            {(customers ?? []).map((c) => (
              <tr key={c.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                <td className="px-4 py-3">
                  <Link to={`/customers/${c.id}`} className="text-gold-light hover:underline">{c.name}</Link>
                </td>
                <td className="px-4 py-3 text-neutral-400">{branchName(c.branch_id)}</td>
                <td className="px-4 py-3 text-neutral-400">{c.phone}</td>
                <td className="px-4 py-3 text-neutral-400">{c.email ?? "—"}</td>
                <td className="px-4 py-3 text-neutral-500">{new Date(c.created_at).toLocaleDateString("en-IN")}</td>
              </tr>
            ))}
            {!isLoading && (customers ?? []).length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">No customers found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
