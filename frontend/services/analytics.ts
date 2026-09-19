import { request } from "./api";

export interface CurrencyMetrics {
  currency: string;
  gmv: string;
  net_sales: string;
  order_count: string;
  avg_order_value: string;
  refund_total: string;
  refund_rate_percent: string;
  platform_fee: string;
  payment_fee: string;
  net_settled: string;
  other_cost: string;
  profit: string;
  profit_margin_percent: string;
}

export interface OverviewResponse {
  window_days: number;
  since: string;
  formulas: Record<string, string>;
  by_currency: Record<string, CurrencyMetrics>;
  note?: string;
}

export interface FinancePayment {
  id: string;
  order_ref: string;
  provider: string;
  amount: string;
  refunded_amount: string;
  currency: string;
  status: string;
}

export interface FinanceRefund {
  id: string;
  payment_id: string;
  amount: string;
  currency: string;
  status: string;
  reason: string | null;
}

export interface FinanceSettlement {
  id: string;
  platform: string;
  period_start: string;
  period_end: string;
  currency: string;
  gross_amount: string;
  platform_fee: string;
  payment_fee: string;
  net_amount: string;
  status: string;
}

export const fetchOverview = (days: number, otherCost = "0") =>
  request<OverviewResponse>(`/analytics/overview?days=${days}&other_cost=${otherCost}`);

export const fetchFormulas = () => request<Record<string, string>>("/analytics/formulas");

export const fetchPayments = () => request<FinancePayment[]>("/finance/payments");
export const fetchRefunds = () => request<FinanceRefund[]>("/finance/refunds");
export const fetchSettlements = () => request<FinanceSettlement[]>("/finance/settlements");
