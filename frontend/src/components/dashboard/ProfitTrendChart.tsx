import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { api } from "@/lib/api";
import type { ProfitTrendPoint } from "@/types";

export function ProfitTrendChart({ branchId }: { branchId?: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "profit-trend", branchId],
    queryFn: async () =>
      (await api.get<ProfitTrendPoint[]>("/dashboard/profit-trend", {
        params: { months: 12, ...(branchId ? { branch_id: branchId } : {}) },
      })).data,
  });

  if (isLoading) return <div className="text-neutral-500 text-sm">Loading trend…</div>;
  if (!data?.length) return <div className="text-neutral-500 text-sm">No data yet.</div>;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#C9A227" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#C9A227" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="expGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#E74C3C" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#E74C3C" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#222226" />
        <XAxis dataKey="period" stroke="#8a8a93" fontSize={12} />
        <YAxis stroke="#8a8a93" fontSize={12} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
        <Tooltip
          contentStyle={{ background: "#18181B", border: "1px solid #33333A", borderRadius: 8, fontSize: 12 }}
          formatter={(value: number) => `₹${value.toLocaleString("en-IN")}`}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#C9A227" fill="url(#revGrad)" strokeWidth={2} />
        <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#E74C3C" fill="url(#expGrad)" strokeWidth={2} />
        <Area type="monotone" dataKey="net_profit" name="Net Profit" stroke="#2ECC71" fill="transparent" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
