"use client";

import { Button, Card, Empty, Select, Tag, Typography } from "antd";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import {
  clearCustomerSession,
  fetchMyOrders,
  type StorefrontOrder,
} from "@/services/saleor";

export default function AccountPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [orders, setOrders] = useState<StorefrontOrder[]>([]);
  const [status, setStatus] = useState("ALL");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(
    (opts?: { silent?: boolean }) => {
      if (!opts?.silent) setLoading(true);
      return fetchMyOrders()
        .then((page) => {
          setEmail(page.email);
          setOrders(page.orders);
        })
        .finally(() => setLoading(false));
    },
    []
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (loading) {
    return (
      <StorefrontLayout>
        <Card>
          <Empty description="加载中" />
        </Card>
      </StorefrontLayout>
    );
  }

  if (!email) {
    return (
      <StorefrontLayout>
        <Card style={{ maxWidth: 560, margin: "40px auto", textAlign: "center" }}>
          <Empty description="登录后查看订单和账户信息">
            <Button type="primary" onClick={() => window.dispatchEvent(new Event("sf-open-auth"))}>
              登录 / 注册
            </Button>
          </Empty>
        </Card>
      </StorefrontLayout>
    );
  }

  return (
    <StorefrontLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          我的账户
        </Typography.Title>
        <Button
          onClick={() => {
            clearCustomerSession();
            refresh({ silent: true });
            router.push("/");
          }}
        >
          退出登录
        </Button>
      </div>
      <Typography.Paragraph style={{ marginTop: 8 }}>
        <Tag color="blue">{email}</Tag>
        <Link href="/account/addresses" style={{ marginLeft: 16 }}>管理收货地址</Link>
        <Link href="/favorites" style={{ marginLeft: 16 }}>我的收藏</Link>
      </Typography.Paragraph>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography.Title level={4}>我的订单</Typography.Title>
        <Select value={status} onChange={setStatus} options={[{ value: "ALL", label: "全部状态" }, { value: "UNFULFILLED", label: "待处理" }, { value: "FULFILLED", label: "已完成" }]} />
      </div>
      {orders.filter((o) => status === "ALL" || o.status === status).length === 0 ? (
        <Empty description="还没有订单" />
      ) : (
        orders.filter((o) => status === "ALL" || o.status === status).map((o) => (
          <Card key={o.id} style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
              <div>
                <Link href={`/order/${o.number}`}>
                  <Typography.Text strong>订单 #{o.number}</Typography.Text>
                </Link>
                <div>
                  <Typography.Text type="secondary">{o.created}</Typography.Text>
                </div>
              </div>
              <Tag color="processing">{o.status}</Tag>
              <Tag color={o.paymentStatus === "FULLY_CHARGED" ? "success" : "warning"}>{o.paymentStatus}</Tag>
              <Typography.Text strong>
                {o.total ? `${o.total.currency} ${o.total.amount.toFixed(2)}` : "-"}
              </Typography.Text>
              <Link href={`/order/${o.number}`}>
                <Button size="small">查看明细</Button>
              </Link>
            </div>
          </Card>
        ))
      )}
    </StorefrontLayout>
  );
}
