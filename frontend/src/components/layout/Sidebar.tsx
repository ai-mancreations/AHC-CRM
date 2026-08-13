import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Users, Phone, CalendarDays, UserSquare2, Boxes,
  Receipt, Wallet, Megaphone, Settings, ShieldCheck, Sparkles,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/leads", label: "Leads", icon: Users },
  { to: "/calls-followups", label: "Calls & Follow-Ups", icon: Phone },
  { to: "/appointments", label: "Appointments", icon: CalendarDays },
  { to: "/customers", label: "Customers", icon: UserSquare2 },
  { to: "/inventory", label: "Inventory", icon: Boxes },
  { to: "/invoices", label: "Billing", icon: Receipt },
  { to: "/expenses", label: "Expenses", icon: Wallet },
  { to: "/marketing", label: "Marketing", icon: Megaphone },
  { to: "/ai-assistant", label: "AI Assistant", icon: Sparkles },
];

export function Sidebar() {
  const { user } = useAuth();

  return (
    <aside className="w-64 shrink-0 bg-charcoal-900 border-r border-charcoal-border flex flex-col h-screen sticky top-0">
      <div className="px-6 py-6 border-b border-charcoal-border">
        <div className="font-display text-xl text-gold-light leading-tight">American</div>
        <div className="font-display text-xl text-gold-light leading-tight -mt-1">Hair Club</div>
        <div className="text-xs text-neutral-500 mt-1 tracking-wide">CRM &amp; Operations</div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                isActive
                  ? "bg-charcoal-700 text-gold-light border border-gold/30"
                  : "text-neutral-400 hover:text-neutral-100 hover:bg-charcoal-800"
              }`
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}

        {user?.role === "SUPER_ADMIN" && (
          <>
            <div className="pt-4 pb-1 px-3 text-[11px] uppercase tracking-wider text-neutral-600">
              Administration
            </div>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                  isActive
                    ? "bg-charcoal-700 text-gold-light border border-gold/30"
                    : "text-neutral-400 hover:text-neutral-100 hover:bg-charcoal-800"
                }`
              }
            >
              <Settings size={17} /> Settings
            </NavLink>
            <NavLink
              to="/audit-log"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                  isActive
                    ? "bg-charcoal-700 text-gold-light border border-gold/30"
                    : "text-neutral-400 hover:text-neutral-100 hover:bg-charcoal-800"
                }`
              }
            >
              <ShieldCheck size={17} /> Audit Log
            </NavLink>
          </>
        )}
      </nav>

      <div className="px-4 py-4 border-t border-charcoal-border text-xs text-neutral-500">
        {user?.name} · <span className="text-gold-light/80">{user?.role.replace("_", " ")}</span>
      </div>
    </aside>
  );
}
