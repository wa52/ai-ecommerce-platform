"use client";

import { Button, Card, Empty, Form, Input, message, Tag, Typography } from "antd";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import {
  clearCustomerSession,
  customerLogin,
  customerRegister,
  fetchMyOrders,
  type StorefrontOrder,
} from "@/services/saleor";

export default function AccountPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [orders, setOrders] = useState<StorefrontOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

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

  async function doLogin(values: { email: string; password: string }) {
    setBusy(true);
    try {
      await customerLogin(values.email, values.password);
      await refresh({ silent: true });
      messageApi.success("登录成功");
    } catch (e) {
      messageApi.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doRegister(values: { email: string; password: string }) {
    setBusy(true);
    try {
      await customerRegister(values.email, values.password);
      messageApi.success("注册成功，请登录");
    } catch (e) {
      messageApi.error(String(e));
    } finally {
      setBusy(false);
    }
  }

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
        {contextHolder}
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          <Card title="登录" style={{ flex: 1, minWidth: 340 }}>
            <Form layout="vertical" onFinish={doLogin}>
              <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email" }]}>
                <Input />
              </Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={busy} block>
                登录
              </Button>
            </Form>
          </Card>
          <Card title="注册" style={{ flex: 1, minWidth: 340 }}>
            <Form layout="vertical" onFinish={doRegister}>
              <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email" }]}>
                <Input />
              </Form.Item>
              <Form.Item name="password" label="密码（8 位以上，含大小写数字）" rules={[{ required: true, min: 8 }]}>
                <Input.Password />
              </Form.Item>
              <Button htmlType="submit" loading={busy} block>
                创建账户
              </Button>
            </Form>
          </Card>
        </div>
      </StorefrontLayout>
    );
  }

  return (
    <StorefrontLayout>
      {contextHolder}
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
      </Typography.Paragraph>
      <Typography.Title level={4}>我的订单</Typography.Title>
      {orders.length === 0 ? (
        <Empty description="还没有订单" />
      ) : (
        orders.map((o) => (
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
