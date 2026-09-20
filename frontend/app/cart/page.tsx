"use client";

import { Button, Card, InputNumber, message, Popconfirm, Result, Skeleton, Typography } from "antd";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import {
  checkoutLineDelete,
  checkoutLinesUpdate,
  checkoutRetrieve,
  type Checkout,
} from "@/services/saleor";

function money(m: { amount: number; currency: string } | null | undefined) {
  return m && typeof m.amount === "number" && m.currency ? `${m.currency} ${m.amount.toFixed(2)}` : "-";
}

export default function CartPage() {
  const router = useRouter();
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyLineId, setBusyLineId] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  const reload = useCallback(
    (opts?: { silent?: boolean }) => {
      if (!opts?.silent) setLoading(true);
      return checkoutRetrieve()
        .then(setCheckout)
        .catch((e) => messageApi.error(String(e)))
        .finally(() => setLoading(false));
    },
    [messageApi]
  );

  useEffect(() => {
    reload().then(() => {
      window.dispatchEvent(new Event("sf-cart-changed"));
    });
  }, [reload]);

  async function updateQty(lineId: string, quantity: number) {
    if (quantity < 1) {
      await removeLine(lineId);
      return;
    }
    setBusyLineId(lineId);
    try {
      const next = await checkoutLinesUpdate(lineId, quantity);
      setCheckout(next);
    } catch (e) {
      messageApi.error(String(e));
      await reload({ silent: true });
    } finally {
      setBusyLineId(null);
      window.dispatchEvent(new Event("sf-cart-changed"));
    }
  }

  async function removeLine(lineId: string) {
    setBusyLineId(lineId);
    try {
      const next = await checkoutLineDelete(lineId);
      setCheckout(next);
    } catch (e) {
      messageApi.error(String(e));
      await reload({ silent: true });
    } finally {
      setBusyLineId(null);
      window.dispatchEvent(new Event("sf-cart-changed"));
    }
  }

  if (loading) {
    return (
      <StorefrontLayout>
        <Skeleton active paragraph={{ rows: 5 }} />
      </StorefrontLayout>
    );
  }

  const lines = checkout?.lines ?? [];
  if (lines.length === 0) {
    return (
      <StorefrontLayout>
        {contextHolder}
        <Result title="购物车是空的" extra={<Button type="primary" onClick={() => router.push("/")}>去逛逛</Button>} />
      </StorefrontLayout>
    );
  }

  const subtotal = lines.reduce((s, l) => s + (l.totalPrice?.amount ?? 0), 0);
  const currency = lines[0]?.totalPrice?.currency ?? "USD";
  return (
    <StorefrontLayout>
      {contextHolder}
      <Typography.Title level={3}>购物车</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        {lines.map((l) => (
          <div
            key={l.id}
            style={{ display: "flex", alignItems: "center", gap: 16, padding: "12px 0", borderBottom: "1px solid #f0f0f0" }}
          >
            <div style={{ width: 64, height: 64, background: "#fafafa", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>
              🛍️
            </div>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>{l.variant.name}</Typography.Text>
              <div>
                <Typography.Text type="secondary">SKU：{l.variant.sku ?? "-"}</Typography.Text>
              </div>
            </div>
            <InputNumber
              min={1}
              size="small"
              value={l.quantity}
              disabled={busyLineId === l.id}
              onChange={(v) => (v ? updateQty(l.id, v) : undefined)}
            />
            <Typography.Text style={{ width: 120, textAlign: "right" }}>{money(l.totalPrice)}</Typography.Text>
            <Popconfirm title="删除该商品？" onConfirm={() => removeLine(l.id)}>
              <Button size="small" danger disabled={busyLineId === l.id}>
                删除
              </Button>
            </Popconfirm>
          </div>
        ))}
      </Card>
      <div style={{ textAlign: "right" }}>
        <Typography.Title level={4}>
          小计：{currency} {subtotal.toFixed(2)}
        </Typography.Title>
        <Button type="primary" size="large" onClick={() => router.push("/checkout")}>
          去结算
        </Button>
      </div>
    </StorefrontLayout>
  );
}
