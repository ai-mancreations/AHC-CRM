import { ReactNode } from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

export function KpiCard({
  label, value, trend, icon,
}: {
  label: string;
  value: string;
  trend?: number; // positive or negative percent
  icon?: ReactNode;
}) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div className="text-xs text-neutral-500 uppercase tracking-wide">{label}</div>
        {icon && <div className="text-gold/70">{icon}</div>}
      </div>
      <div className="kpi-value mt-2">{value}</div>
      {trend !== undefined && (
        <div className={`flex items-center gap-1 text-xs mt-2 ${trend >= 0 ? "text-emerald-400" : "text-red-400"}`}>
          {trend >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          {Math.abs(trend).toFixed(1)}% vs last period
        </div>
      )}
    </div>
  );
}
