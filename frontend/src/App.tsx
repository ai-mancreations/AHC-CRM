import { Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/context/AuthContext";
import { BranchProvider } from "@/context/BranchContext";
import { ProtectedRoute } from "@/components/shared/ProtectedRoute";
import { AppLayout } from "@/components/layout/AppLayout";

import LoginPage from "@/pages/LoginPage";
import TodayDashboardPage from "@/pages/TodayDashboardPage";
import LeadsKanbanPage from "@/pages/LeadsKanbanPage";
import CallsFollowUpsPage from "@/pages/CallsFollowUpsPage";
import AppointmentsPage from "@/pages/AppointmentsPage";
import CustomersPage from "@/pages/CustomersPage";
import Customer360Page from "@/pages/Customer360Page";
import InventoryPage from "@/pages/InventoryPage";
import InvoicesPage from "@/pages/InvoicesPage";
import ExpensesPage from "@/pages/ExpensesPage";
import MarketingPage from "@/pages/MarketingPage";
import AiAssistantPage from "@/pages/AiAssistantPage";
import SettingsPage from "@/pages/SettingsPage";
import AuditLogPage from "@/pages/AuditLogPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 15000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BranchProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<TodayDashboardPage />} />
                <Route path="/leads" element={<LeadsKanbanPage />} />
                <Route path="/calls-followups" element={<CallsFollowUpsPage />} />
                <Route path="/appointments" element={<AppointmentsPage />} />
                <Route path="/customers" element={<CustomersPage />} />
                <Route path="/customers/:id" element={<Customer360Page />} />
                <Route path="/inventory" element={<InventoryPage />} />
                <Route path="/invoices" element={<InvoicesPage />} />
                <Route path="/expenses" element={<ExpensesPage />} />
                <Route path="/marketing" element={<MarketingPage />} />
                <Route path="/ai-assistant" element={<AiAssistantPage />} />
              </Route>
            </Route>

            <Route element={<ProtectedRoute requireSuperAdmin />}>
              <Route element={<AppLayout />}>
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/audit-log" element={<AuditLogPage />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BranchProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
