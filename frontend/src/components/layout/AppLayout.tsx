import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const TITLES: Record<string, string> = {
  "/": "Today's Business",
  "/leads": "Lead Pipeline",
  "/calls-followups": "Calls & Follow-Ups",
  "/appointments": "Cabin & Slot Booking",
  "/customers": "Customers",
  "/inventory": "Inventory",
  "/invoices": "Billing & Invoicing",
  "/expenses": "Expenses",
  "/marketing": "Marketing",
  "/ai-assistant": "AI Assistant",
  "/settings": "Settings",
  "/audit-log": "Audit Log",
};

export function AppLayout() {
  const { pathname } = useLocation();
  const title = TITLES[pathname] ?? "American Hair Club";

  return (
    <div className="flex min-h-screen bg-charcoal-950">
      <Sidebar />
      <div className="flex-1 min-w-0">
        <Topbar title={title} />
        <main className="p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
