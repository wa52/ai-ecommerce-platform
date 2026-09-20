export const SALEOR_API_URL =
  process.env.NEXT_PUBLIC_SALEOR_API_URL ?? "http://localhost:8000/graphql/";

export const SALEOR_PAYMENT_GATEWAY =
  process.env.NEXT_PUBLIC_SALEOR_PAYMENT_GATEWAY ?? "mirumee.payments.dummy";

export const SALEOR_PAYMENT_LABEL =
  SALEOR_PAYMENT_GATEWAY === "mirumee.payments.dummy" ? "沙箱支付" : "支付宝";

const CHECKOUT_KEY = "sf_checkout_id";
const CHECKOUT_QTY_KEY = "sf_checkout_qty";
const CUSTOMER_KEY = "sf_customer_token";
const CUSTOMER_EMAIL_KEY = "sf_customer_email";
const LAST_ORDER_KEY = "sf_last_order";

export interface Money {
  amount: number;
  currency: string;
}

export interface StorefrontVariant {
  id: string;
  name: string;
  sku: string | null;
  quantityAvailable: number | null;
  price: Money | null;
}

export interface StorefrontProduct {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  price: Money | null;
  isAvailableForPurchase: boolean;
  variants: StorefrontVariant[];
  imageUrl: string | null;
  imageAlt: string | null;
  media: { url: string; alt: string | null }[];
  category: { name: string; slug: string } | null;
}

export interface StorefrontProductPage {
  items: StorefrontProduct[];
  totalCount: number;
  hasNextPage: boolean;
  endCursor: string | null;
}

export function getBookCoverFallback(slug: string): string {
  const covers: [string, string][] = [
    ["huo-zhe", "alive.png"],
    ["bai-nian-gu-du", "bai-nian-gu-du.png"],
    ["ren-lei-jian-shi", "alive.png"],
    ["yuan-ze", "principles.png"],
    ["xiao-wang-zi", "little-prince.png"],
    ["jie-you-za-huo-dian", "worry-shop.png"],
    ["zhi-shen-shi-nei", "inside-economy.png"],
    ["na-wa-er-bao-dian", "naval.png"],
    ["bei-tao-yan-de-yong-qi", "courage.png"],
    ["yun-bian-you-ge-xiao-mai-bu", "cloud-town.png"],
  ];
  const match = covers.find(([key]) => slug.includes(key));
  return `/book-covers/${match?.[1] ?? "alive.png"}`;
}

export interface CheckoutLine {
  id: string;
  quantity: number;
  variant: { id: string; name: string; sku: string | null };
  unitPrice: Money | null;
  totalPrice: Money | null;
}

export interface Checkout {
  id: string;
  token: string;
  lines: CheckoutLine[];
  subtotal: Money | null;
  total: Money | null;
  shippingMethods: { id: string; name: string }[];
  email: string | null;
}

export interface StorefrontOrder {
  id: string;
  number: string;
  token: string | null;
  status: string;
  paymentStatus: string;
  created: string;
  total: Money | null;
  lines: { quantity: number; variantName: string; unitPrice: Money | null }[];
}

export class SaleorError extends Error {}

const SALEOR_REQUEST_TIMEOUT_MS = 8_000;

interface GqlPayload {
  data?: Record<string, unknown>;
  errors?: { message: string | null }[];
}

export async function saleorFetch<T>(
  query: string,
  variables: Record<string, unknown> = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), SALEOR_REQUEST_TIMEOUT_MS);
  try {
    const resp = await fetch(SALEOR_API_URL, {
      method: "POST",
      headers,
      body: JSON.stringify({ query, variables }),
      cache: "no-store",
      signal: controller.signal,
    });
    if (!resp.ok) throw new SaleorError(`Saleor 请求失败（HTTP ${resp.status}）`);
    const body = (await resp.json()) as GqlPayload;
    const firstError = body.errors?.[0]?.message;
    if (firstError) throw new SaleorError(firstError);
    if (!body.data) throw new SaleorError("Saleor 返回空数据");
    return body.data as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new SaleorError("Saleor 服务响应超时，请确认 Docker 与 Saleor API 已启动");
    }
    if (error instanceof TypeError) {
      throw new SaleorError("无法连接 Saleor，请确认 Docker 与 Saleor API 已启动");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function errText(errors: { field: string | null; message: string | null }[] | null | undefined) {
  if (!errors || errors.length === 0) return null;
  return errors.map((e) => (e.field ? `${e.field}: ${e.message ?? ""}` : e.message ?? "")).join("; ");
}

function normalizeMediaUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    if (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") {
      return `${parsed.pathname}${parsed.search}`;
    }
  } catch {
    // Saleor may return a relative URL already.
  }
  return raw;
}

// Saleor 的金额字段是 TaxedMoney 形状 { gross: { amount, currency } }，这里归一化为 { amount, currency }。
function taxedToMoney(t: { gross?: { amount?: number | null; currency?: string | null } } | null | undefined): Money | null {
  const g = t?.gross;
  if (!g || typeof g.amount !== "number" || !g.currency) return null;
  return { amount: g.amount, currency: g.currency };
}

function normalizeCheckout(raw: Record<string, unknown>): Checkout {
  const lines = ((raw.lines as Record<string, unknown>[]) ?? []).map((l) => ({
    id: String(l.id),
    quantity: Number(l.quantity),
    variant: l.variant as CheckoutLine["variant"],
    unitPrice: taxedToMoney(l.unitPrice as { gross?: { amount?: number; currency?: string } }),
    totalPrice: taxedToMoney(l.totalPrice as { gross?: { amount?: number; currency?: string } }),
  }));
  return {
    id: String(raw.id),
    token: String(raw.token ?? ""),
    lines,
    subtotal: taxedToMoney(raw.subtotal as { gross?: { amount?: number; currency?: string } }),
    total: taxedToMoney(raw.total as { gross?: { amount?: number; currency?: string } }),
    shippingMethods: ((raw.shippingMethods as Record<string, unknown>[]) ?? []).map((m) => ({
      id: String(m.id),
      name: String(m.name ?? ""),
    })),
    email: raw.email ? String(raw.email) : null,
  };
}

const PRODUCTS_QUERY = `
query StorefrontProducts($first: Int!, $after: String, $search: String) {
  products(first: $first, after: $after, channel: "default-channel", filter: { search: $search }) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id name slug isAvailableForPurchase
        description
        media { url alt }
        category { name slug }
        pricing { priceRange { start { gross { amount currency } } } }
        variants { id name sku quantityAvailable }
      }
    }
  }
}
`;

export async function fetchProducts(params: {
  first?: number;
  after?: string | null;
  search?: string | null;
}): Promise<StorefrontProductPage> {
  const data = await saleorFetch<{
    products: {
      totalCount: number | null;
      pageInfo: { hasNextPage: boolean; endCursor: string | null };
      edges: { node: Record<string, unknown> }[];
    } | null;
  }>(PRODUCTS_QUERY, {
    first: params.first ?? 12,
    after: params.after ?? undefined,
    search: params.search ?? undefined,
  });
  const conn = data.products;
  const items = (conn?.edges ?? []).map((e) => {
    const n = e.node as {
      id: string;
      name: string;
      slug: string;
      isAvailableForPurchase: boolean;
      description: string | null;
      media?: { url: string; alt: string | null }[];
      category?: { name: string; slug: string } | null;
      pricing?: { priceRange?: { start?: { gross?: Money } } } | null;
      variants: { id: string; name: string; sku: string | null; quantityAvailable: number | null }[];
    };
    const product: StorefrontProduct = {
      id: n.id,
      name: n.name,
      slug: n.slug,
      description: n.description,
      price: n.pricing?.priceRange?.start?.gross ?? null,
      isAvailableForPurchase: n.isAvailableForPurchase,
      variants: n.variants.map((v) => ({ ...v, price: null })),
      imageUrl: normalizeMediaUrl(n.media?.[0]?.url),
      imageAlt: n.media?.[0]?.alt ?? null,
      media: (n.media ?? []).map((m) => ({ url: normalizeMediaUrl(m.url) ?? "", alt: m.alt ?? null })),
      category: n.category ?? null,
    };
    return product;
  });
  return {
    items,
    totalCount: conn?.totalCount ?? items.length,
    hasNextPage: conn?.pageInfo.hasNextPage ?? false,
    endCursor: conn?.pageInfo.endCursor ?? null,
  };
}

const PRODUCT_BY_SLUG_QUERY = `
query StorefrontProduct($slug: String!) {
  product(slug: $slug, channel: "default-channel") {
    id name slug isAvailableForPurchase
    description
    media { url alt }
    category { name slug }
    pricing { priceRange { start { gross { amount currency } } } }
    variants {
      id name sku quantityAvailable
      pricing { price { gross { amount currency } } }
    }
  }
}
`;

export async function fetchProductBySlug(slug: string): Promise<StorefrontProduct | null> {
  const data = await saleorFetch<{ product: Record<string, unknown> | null }>(PRODUCT_BY_SLUG_QUERY, { slug });
  const n = data.product as {
    id: string;
    name: string;
    slug: string;
    isAvailableForPurchase: boolean;
    description: string | null;
    media?: { url: string; alt: string | null }[];
    category?: { name: string; slug: string } | null;
    pricing?: { priceRange?: { start?: { gross?: Money } } } | null;
    variants: {
      id: string;
      name: string;
      sku: string | null;
      quantityAvailable: number | null;
      pricing?: { price?: { gross?: Money } } | null;
    }[] | null;
  } | null;
  if (!n) return null;
  return {
    id: n.id,
    name: n.name,
    slug: n.slug,
    description: n.description,
    price: n.pricing?.priceRange?.start?.gross ?? null,
    isAvailableForPurchase: n.isAvailableForPurchase,
    variants: (n.variants ?? []).map((v) => ({
      id: v.id,
      name: v.name,
      sku: v.sku,
      quantityAvailable: v.quantityAvailable,
      price: v.pricing?.price?.gross ?? null,
    })),
    imageUrl: normalizeMediaUrl(n.media?.[0]?.url),
    imageAlt: n.media?.[0]?.alt ?? null,
    media: (n.media ?? []).map((m) => ({ url: normalizeMediaUrl(m.url) ?? "", alt: m.alt ?? null })),
    category: n.category ?? null,
  };
}

const CHECKOUT_FRAGMENT = `
fragment StoreCheckout on Checkout {
  id token email
  lines {
    id quantity
    variant { id name sku }
    unitPrice { gross { amount currency } }
    totalPrice { gross { amount currency } }
  }
  subtotal: subtotalPrice { gross { amount currency } }
  total: totalPrice { gross { amount currency } }
  shippingMethods { id name }
}
`;

const CHECKOUT_CREATE = `
mutation CheckoutCreate($input: CheckoutCreateInput!) {
  checkoutCreate(input: $input) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_LINES_ADD = `
mutation LinesAdd($id: ID!, $lines: [CheckoutLineInput!]!) {
  checkoutLinesAdd(id: $id, lines: $lines) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_LINE_DELETE = `
mutation LineDelete($id: ID!, $lineId: ID!) {
  checkoutLineDelete(id: $id, lineId: $lineId) {
    checkout { ...StoreCheckout }
    lineId
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_LINES_UPDATE = `
mutation LinesUpdate($id: ID!, $lines: [CheckoutLineUpdateInput!]!) {
  checkoutLinesUpdate(id: $id, lines: $lines) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_RETRIEVE = `
query CheckoutRetrieve($id: ID!) {
  checkout(id: $id) { ...StoreCheckout }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_EMAIL_UPDATE = `
mutation EmailUpdate($id: ID!, $email: String!) {
  checkoutEmailUpdate(id: $id, email: $email) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_SHIPPING_ADDRESS = `
mutation ShippingAddress($id: ID!, $addr: AddressInput!) {
  checkoutShippingAddressUpdate(id: $id, shippingAddress: $addr) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_BILLING_ADDRESS = `
mutation BillingAddress($id: ID!, $addr: AddressInput!) {
  checkoutBillingAddressUpdate(id: $id, billingAddress: $addr) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_DELIVERY_METHOD = `
mutation DeliveryMethod($id: ID!, $methodId: ID!) {
  checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $methodId) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_PAYMENT = `
mutation Payment($id: ID!, $in: PaymentInput!) {
  checkoutPaymentCreate(id: $id, input: $in) {
    checkout { ...StoreCheckout }
    errors { field message }
  }
}
${CHECKOUT_FRAGMENT}
`;

const CHECKOUT_COMPLETE = `
mutation Complete($id: ID!) {
  checkoutComplete(id: $id) {
    order {
      id number token status paymentStatus created
      total { gross { amount currency } }
      lines { quantity variantName unitPrice { gross { amount currency } } }
    }
    errors { field message code }
  }
}
`;

export function getCheckoutId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(CHECKOUT_KEY);
}

export function clearCheckout() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(CHECKOUT_KEY);
  window.localStorage.removeItem(CHECKOUT_QTY_KEY);
}

function recordQuantity(checkout: Checkout) {
  if (typeof window === "undefined") return;
  const qty = checkout.lines.reduce((s, l) => s + l.quantity, 0);
  window.localStorage.setItem(CHECKOUT_QTY_KEY, String(qty));
}

interface ResError {
  field: string | null;
  message: string | null;
  code?: string | null;
}

async function unwrap(payload: { checkout?: Checkout | null; errors?: ResError[] | null } | null): Promise<Checkout> {
  const errors = payload?.errors ?? null;
  if (errors && errors.length > 0) {
    throw new SaleorError(errText(errors) ?? "操作失败");
  }
  const checkout = payload?.checkout;
  if (!checkout) throw new SaleorError("操作失败：未返回购物车");
  const normalized = normalizeCheckout(checkout as unknown as Record<string, unknown>);
  window.localStorage.setItem(CHECKOUT_KEY, normalized.id);
  recordQuantity(normalized);
  return normalized;
}

async function checkoutCreate(input: { variantId: string; quantity: number; email?: string }): Promise<Checkout> {
  const data = await saleorFetch<{
    checkoutCreate: { checkout: Checkout | null; errors: ResError[] | null };
  }>(CHECKOUT_CREATE, {
    input: {
      channel: "default-channel",
      email: input.email ?? undefined,
      lines: [{ quantity: input.quantity, variantId: input.variantId }],
    },
  });
  return unwrap(data.checkoutCreate);
}

export async function checkoutLinesAdd(variantId: string, quantity: number): Promise<Checkout> {
  const existing = getCheckoutId();
  if (!existing) {
    const email = getCustomerEmail() ?? undefined;
    return checkoutCreate({ variantId, quantity, email });
  }
  const data = await saleorFetch<{ checkoutLinesAdd: { checkout: Checkout | null; errors: ResError[] | null } }>(
    CHECKOUT_LINES_ADD,
    { id: existing, lines: [{ quantity, variantId }] }
  );
  return unwrap(data.checkoutLinesAdd);
}

export async function checkoutLineDelete(lineId: string): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{ checkoutLineDelete: { checkout: Checkout | null; errors: ResError[] | null } }>(
    CHECKOUT_LINE_DELETE,
    { id, lineId }
  );
  return unwrap(data.checkoutLineDelete);
}

export async function checkoutLinesUpdate(lineId: string, quantity: number): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{ checkoutLinesUpdate: { checkout: Checkout | null; errors: ResError[] | null } }>(
    CHECKOUT_LINES_UPDATE,
    { id, lines: [{ id: lineId, quantity }] }
  );
  return unwrap(data.checkoutLinesUpdate);
}

export async function checkoutRetrieve(): Promise<Checkout | null> {
  const id = getCheckoutId();
  if (!id) return null;
  const data = await saleorFetch<{ checkout: Checkout | null }>(CHECKOUT_RETRIEVE, { id });
  const checkout = data.checkout;
  if (checkout) {
    const normalized = normalizeCheckout(checkout as unknown as Record<string, unknown>);
    recordQuantity(normalized);
    return normalized;
  }
  clearCheckout();
  return null;
}

export async function checkoutEmailUpdate(email: string): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{ checkoutEmailUpdate: { checkout: Checkout | null; errors: ResError[] | null } }>(
    CHECKOUT_EMAIL_UPDATE,
    { id, email }
  );
  return unwrap(data.checkoutEmailUpdate);
}

export async function checkoutShippingAddressUpdate(addr: Record<string, unknown>): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{
    checkoutShippingAddressUpdate: { checkout: Checkout | null; errors: ResError[] | null };
  }>(CHECKOUT_SHIPPING_ADDRESS, { id, addr });
  return unwrap(data.checkoutShippingAddressUpdate);
}

export async function checkoutBillingAddressUpdate(addr: Record<string, unknown>): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{
    checkoutBillingAddressUpdate: { checkout: Checkout | null; errors: ResError[] | null };
  }>(CHECKOUT_BILLING_ADDRESS, { id, addr });
  return unwrap(data.checkoutBillingAddressUpdate);
}

export async function checkoutDeliveryMethodUpdate(methodId: string): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{
    checkoutDeliveryMethodUpdate: { checkout: Checkout | null; errors: ResError[] | null };
  }>(CHECKOUT_DELIVERY_METHOD, { id, methodId });
  return unwrap(data.checkoutDeliveryMethodUpdate);
}

export async function checkoutPaymentCreate(gateway: string, amount: number): Promise<Checkout> {
  const id = getCheckoutId();
  if (!id) throw new SaleorError("购物车不存在");
  const data = await saleorFetch<{ checkoutPaymentCreate: { checkout: Checkout | null; errors: ResError[] | null } }>(
    CHECKOUT_PAYMENT,
    { id, in: { gateway, token: "sandbox", amount } }
  );
  return unwrap(data.checkoutPaymentCreate);
}

export async function checkoutComplete(): Promise<{
  order: StorefrontOrder | null;
  error: string | null;
}> {
  const id = getCheckoutId();
  if (!id) return { order: null, error: "购物车不存在" };
  const data = await saleorFetch<{
    checkoutComplete: {
      order: Record<string, unknown> | null;
      errors: { field: string | null; message: string | null; code: string | null }[] | null;
    };
  }>(CHECKOUT_COMPLETE, { id });
  const res = data.checkoutComplete;
  const errors = res?.errors ?? [];
  if (!res?.order && errors.length > 0) {
    return { order: null, error: errText(errors) };
  }
  if (!res?.order) return { order: null, error: "下单未成功，请重试" };
  const order = serializeOrder(res.order);
  setLastOrder(order);
  clearCheckout();
  return { order, error: null };
}

// ---------- 客户账户 ----------

export function getCustomerToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(CUSTOMER_KEY);
}

export function getCustomerEmail(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(CUSTOMER_EMAIL_KEY);
}

export function setCustomerSession(token: string, email: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CUSTOMER_KEY, token);
  window.localStorage.setItem(CUSTOMER_EMAIL_KEY, email);
}

export function clearCustomerSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(CUSTOMER_KEY);
  window.localStorage.removeItem(CUSTOMER_EMAIL_KEY);
}

const REGISTER_MUTATION = `
mutation Register($e: String!, $p: String!, $r: String) {
  accountRegister(input: { email: $e, password: $p, redirectUrl: $r }) {
    accountErrors: errors { field message code }
  }
}
`;

const TOKEN_CREATE = `
mutation TokenCreate($e: String!, $p: String!) {
  tokenCreate(email: $e, password: $p) {
    token
    user { email isStaff }
    errors { message }
  }
}
`;

const ME_QUERY = `
query Me {
  me {
    email
    orders(first: 20) { edges { node { ...StoreOrder } } }
  }
}
fragment StoreOrder on Order {
  id number status paymentStatus created token
  total { gross { amount currency } }
  lines { quantity variantName unitPrice { gross { amount currency } } }
}
`;

export async function customerRegister(email: string, password: string): Promise<void> {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const data = await saleorFetch<{ accountRegister: { accountErrors: ResError[] | null } }>(REGISTER_MUTATION, {
    e: email,
    p: password,
    r: `${siteUrl}/account`,
  });
  const errors = data.accountRegister.accountErrors;
  if (errors && errors.length > 0) throw new SaleorError(errText(errors) ?? "注册失败");
}

export async function customerLogin(email: string, password: string): Promise<string> {
  const data = await saleorFetch<{
    tokenCreate: {
      token: string | null;
      user: { email: string; isStaff: boolean } | null;
      errors: { message: string }[] | null;
    };
  }>(TOKEN_CREATE, { e: email, p: password });
  const payload = data.tokenCreate;
  if (payload.errors && payload.errors.length > 0) {
    throw new SaleorError(payload.errors.map((e) => e.message).join("; "));
  }
  if (!payload.token || !payload.user) throw new SaleorError("登录失败");
  setCustomerSession(payload.token, payload.user.email);
  return payload.user.email;
}

export interface CustomerOrderPage {
  email: string | null;
  orders: StorefrontOrder[];
}

export async function fetchMyOrders(): Promise<CustomerOrderPage> {
  const token = getCustomerToken();
  if (!token) return { email: null, orders: [] };
  try {
    const data = await saleorFetch<{
      me: { email: string | null; orders: { edges: { node: Record<string, unknown> }[] } | null } | null;
    }>(ME_QUERY, {}, token);
    const me = data.me;
    if (!me) return { email: null, orders: [] };
    const orders = (me.orders?.edges ?? []).map((e) => serializeOrder(e.node));
    return { email: me.email, orders };
  } catch {
    return { email: null, orders: [] };
  }
}

export function serializeOrder(node: Record<string, unknown>): StorefrontOrder {
  const total = (node.total as { gross?: Money } | null)?.gross ?? null;
  return {
    id: String(node.id),
    number: String(node.number),
    token: node.token ? String(node.token) : null,
    status: String(node.status),
    paymentStatus: String(node.paymentStatus),
    created: String(node.created),
    total,
    lines: ((node.lines as Record<string, unknown>[]) ?? []).map((l) => ({
      quantity: Number(l.quantity),
      variantName: String(l.variantName),
      unitPrice: (l.unitPrice as { gross?: Money } | null)?.gross ?? null,
    })),
  };
}

export function setLastOrder(order: StorefrontOrder) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LAST_ORDER_KEY, JSON.stringify(order));
}

export function getLastOrder(): StorefrontOrder | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(LAST_ORDER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StorefrontOrder;
  } catch {
    return null;
  }
}
