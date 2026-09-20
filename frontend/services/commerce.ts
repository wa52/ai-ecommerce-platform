import { request } from "./api";

export interface Page {
  total_count: number;
  has_next_page: boolean;
  end_cursor: string | null;
}

export interface Product {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  product_type: string | null;
  channels: string[];
}

export interface OrderItem {
  id: string;
  product_name: string;
  sku: string | null;
  quantity: number;
  unit_amount: string;
  currency: string;
}

export interface Order {
  id: string;
  number: string;
  status: string;
  payment_status: string;
  channel: string | null;
  total_amount: string;
  currency: string;
  created_at: string;
  items: OrderItem[];
  fulfillments?: { id: string; status: string; tracking_number: string; created_at: string }[];
}

export interface ProductPage {
  items: Product[];
  page: Page;
}

export interface OrderPage {
  items: Order[];
  page: Page;
}

export interface Stock {
  variant_id: string;
  sku: string | null;
  warehouse_id: string;
  warehouse_name: string;
  quantity: number;
}

export interface StockPage { items: Stock[]; page: Page }
export interface Customer { id: string; email: string; first_name: string; last_name: string; date_joined: string; is_active: boolean; order_count: number }
export interface CustomerPage { items: Customer[]; page: Page }
export interface Category { id: string; name: string; slug: string; level: number }
export interface CategoryPage { items: Category[]; page: Page }

export function fetchProducts(params: { page: number; pageSize: number; search?: string }) {
  const query = new URLSearchParams({ first: String(params.pageSize) });
  if (params.search) query.set("search", params.search);
  return request<ProductPage>(`/commerce/products?${query.toString()}`);
}

export function createProduct(input: { name: string; slug: string; description?: string }) {
  return request<Product>("/commerce/products", { method: "POST", body: JSON.stringify(input) });
}

export function deleteProduct(id: string) {
  return request<void>(`/commerce/products/${id}`, { method: "DELETE" });
}

export function fetchOrders(params: { page: number; pageSize: number }) {
  const query = new URLSearchParams({ first: String(params.pageSize) });
  return request<OrderPage>(`/commerce/orders?${query.toString()}`);
}

export function cancelOrder(id: string) { return request<Order>(`/commerce/orders/${id}/cancel`, { method: "POST" }); }
export function markOrderPaid(id: string, transaction_reference?: string) { return request<Order>(`/commerce/orders/${id}/mark-paid`, { method: "POST", body: JSON.stringify({ transaction_reference }) }); }
export function fulfillOrder(id: string, lines: { orderLineId: string; quantity: number }[]) { return request<Record<string, unknown>>(`/commerce/orders/${id}/fulfill`, { method: "POST", body: JSON.stringify({ lines }) }); }

export function fetchInventory(params: { page: number; pageSize: number }) {
  const query = new URLSearchParams({ first: String(params.pageSize) });
  return request<StockPage>(`/commerce/inventory?${query.toString()}`);
}

export function fetchCustomers(params: { page: number; pageSize: number; search?: string }) {
  const query = new URLSearchParams({ first: String(params.pageSize) }); if (params.search) query.set("search", params.search);
  return request<CustomerPage>(`/commerce/customers?${query.toString()}`);
}
export function fetchCategories() { return request<CategoryPage>("/commerce/categories?first=100"); }
