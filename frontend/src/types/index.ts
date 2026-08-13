export type Role = "SUPER_ADMIN" | "MANAGER";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  phone?: string | null;
  photo_url?: string | null;
}

export interface Branch {
  id: string;
  name: string;
  code: string;
  city: string;
  state: string;
  state_code: string;
  gstin: string;
  is_active: boolean;
}

export interface SettingsItem {
  id: string;
  list_type: string;
  name: string;
  sort_order: number;
  extra: Record<string, any>;
  is_active: boolean;
  is_archived: boolean;
}

export interface Lead {
  id: string;
  branch_id: string;
  name: string;
  phone: string;
  email?: string | null;
  lead_source_id: string;
  lead_status_id: string;
  visit_reason: string;
  campaign_name?: string | null;
  notes?: string | null;
  converted_customer_id?: string | null;
  created_at: string;
}

export interface Customer {
  id: string;
  branch_id: string;
  name: string;
  phone: string;
  email?: string | null;
  address?: string | null;
  created_at: string;
}

export interface Invoice {
  id: string;
  branch_id: string;
  customer_id: string;
  invoice_number: string;
  financial_year: string;
  grand_total: number;
  amount_paid: number;
  status: string;
  issued_at: string;
}

export interface ProfitTrendPoint {
  period: string;
  revenue: number;
  expenses: number;
  net_profit: number;
  margin_pct: number;
}
