import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

interface Campaign {
  id: string;
  platform: string;
  campaign_name: string;
  spend: number;
  leads_generated: number;
  conversions: number;
  cpl: number;
  cac: number;
  roas: number;
}

export default function MarketingPage() {
  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["marketing", "campaigns"],
    queryFn: async () => (await api.get<Campaign[]>("/marketing/campaigns")).data,
  });

  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
            <th className="px-4 py-3 font-medium">Campaign</th>
            <th className="px-4 py-3 font-medium">Platform</th>
            <th className="px-4 py-3 font-medium">Spend</th>
            <th className="px-4 py-3 font-medium">Leads</th>
            <th className="px-4 py-3 font-medium">Conversions</th>
            <th className="px-4 py-3 font-medium">CPL</th>
            <th className="px-4 py-3 font-medium">CAC</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan={7} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
          {(campaigns ?? []).map((c) => (
            <tr key={c.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
              <td className="px-4 py-3 text-neutral-200">{c.campaign_name}</td>
              <td className="px-4 py-3 text-neutral-500">{c.platform.replace("_", " ")}</td>
              <td className="px-4 py-3">{inr(c.spend)}</td>
              <td className="px-4 py-3">{c.leads_generated}</td>
              <td className="px-4 py-3">{c.conversions}</td>
              <td className="px-4 py-3 text-gold-light">{inr(c.cpl)}</td>
              <td className="px-4 py-3 text-gold-light">{inr(c.cac)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
