import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useBranch } from "@/context/BranchContext";
import { api } from "@/lib/api";

export function Topbar({ title }: { title: string }) {
  const { logout } = useAuth();
  const { branches, selectedBranchId, setSelectedBranchId } = useBranch();

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: async () => (await api.get("/notifications/unread-count")).data.count as number,
    refetchInterval: 30000,
  });

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between px-8 py-5 bg-charcoal-950/90 backdrop-blur border-b border-charcoal-border">
      <h1 className="font-display text-2xl text-neutral-100">{title}</h1>

      <div className="flex items-center gap-4">
        <select
          className="input-field !py-1.5 text-xs"
          value={selectedBranchId ?? "ALL"}
          onChange={(e) => setSelectedBranchId(e.target.value === "ALL" ? null : e.target.value)}
        >
          <option value="ALL">All Branches</option>
          {branches.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>

        <button className="relative text-neutral-400 hover:text-gold-light transition">
          <Bell size={19} />
          {!!unread && (
            <span className="absolute -top-1.5 -right-1.5 bg-gold text-charcoal-950 text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>

        <button onClick={logout} className="text-neutral-400 hover:text-gold-light transition" title="Log out">
          <LogOut size={19} />
        </button>
      </div>
    </header>
  );
}
