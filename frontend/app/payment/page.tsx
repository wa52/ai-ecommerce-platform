"use client";

import { CheckCircleOutlined, CreditCardOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Button, Card, Divider, List, message, Result, Skeleton, Steps, Tag, Typography } from "antd";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import styles from "./payment.module.css";
import {
  checkoutComplete,
  checkoutPaymentCreate,
  checkoutRetrieve,
  getCustomerEmail,
  SALEOR_PAYMENT_GATEWAY,
  SALEOR_PAYMENT_LABEL,
  type Checkout,
} from "@/services/saleor";

export default function PaymentPage() {
  const router = useRouter();
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  const reload = useCallback(() => {
    setLoading(true);
    checkoutRetrieve()
      .then(setCheckout)
      .catch((error) => messageApi.error(String(error)))
      .finally(() => setLoading(false));
  }, [messageApi]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function confirmPayment() {
    if (!checkout) return;
    setBusy(true);
    try {
      const total = checkout.total?.amount ?? 0;
      if (!(total > 0)) throw new Error("订单金额异常");
      await checkoutPaymentCreate(SALEOR_PAYMENT_GATEWAY, total);
      const completed = await checkoutComplete();
      if (!completed.order) throw new Error(completed.error ?? "支付未完成，请重试");
      router.push(`/order/${completed.order.number}`);
    } catch (error) {
      messageApi.error(String(error));
      reload();
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <StorefrontLayout><Skeleton active paragraph={{ rows: 8 }} /></StorefrontLayout>;
  }

  if (!checkout || checkout.lines.length === 0) {
    return (
      <StorefrontLayout>
        {contextHolder}
        <Result status="info" title="没有待支付订单" subTitle="请先从购物车进入结算。" extra={<Button type="primary" onClick={() => router.push("/cart")}>返回购物车</Button>} />
      </StorefrontLayout>
    );
  }

  const total = checkout.total?.amount ?? checkout.subtotal?.amount ?? 0;
  const currency = checkout.total?.currency ?? checkout.subtotal?.currency ?? "USD";
  const isSandbox = SALEOR_PAYMENT_GATEWAY === "mirumee.payments.dummy";

  return (
    <StorefrontLayout>
      {contextHolder}
      <Typography.Title level={3}>选择支付方式</Typography.Title>
      <Steps current={1} items={[{ title: "收货信息" }, { title: "支付" }, { title: "完成" }]} style={{ maxWidth: 640, marginBottom: 24 }} />
      <div className={styles.paymentLayout}>
        <Card title="支付方式" extra={<Tag color={isSandbox ? "gold" : "blue"}>{SALEOR_PAYMENT_LABEL}</Tag>}>
          <Card size="small" style={{ borderColor: "#1677ff", background: "#f5f9ff" }}>
            <List.Item>
              <List.Item.Meta
                avatar={<CreditCardOutlined style={{ fontSize: 26, color: "#1677ff" }} />}
                title={isSandbox ? "沙箱支付" : "支付宝"}
                description={isSandbox ? "开发演示环境：不会产生真实扣款。" : "通过已配置的支付网关完成支付。"}
              />
              <CheckCircleOutlined style={{ color: "#1677ff", fontSize: 20 }} />
            </List.Item>
          </Card>
          <Card size="small" style={{ marginTop: 12, background: "#fafafa" }}>
            <List.Item>
              <List.Item.Meta
                avatar={<SafetyCertificateOutlined style={{ fontSize: 26, color: "#52c41a" }} />}
                title="支付安全说明"
                description="订单会在支付确认后创建；密码和支付密钥不会保存在商城前端。"
              />
            </List.Item>
          </Card>
          <Divider />
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {isSandbox
              ? "当前为本地演示模式，点击确认后会模拟支付成功并生成订单。接入正式支付宝前，请先在 Saleor Payment App 中配置商户参数。"
              : `支付账户：${getCustomerEmail() ?? checkout.email ?? "当前订单邮箱"}`}
          </Typography.Paragraph>
          <Button type="primary" size="large" block loading={busy} onClick={confirmPayment} style={{ marginTop: 20 }}>
            {isSandbox ? "确认模拟支付" : "确认支付"}
          </Button>
          <Button type="link" block onClick={() => router.push("/checkout")} disabled={busy}>返回修改收货信息</Button>
        </Card>

        <Card title="订单摘要">
          {checkout.lines.map((line) => (
            <div key={line.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "8px 0" }}>
              <Typography.Text ellipsis>{line.variant.name} × {line.quantity}</Typography.Text>
              <Typography.Text>{line.totalPrice ? `${line.totalPrice.currency} ${line.totalPrice.amount.toFixed(2)}` : "-"}</Typography.Text>
            </div>
          ))}
          <Divider style={{ margin: "12px 0" }} />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <Typography.Text strong>应付合计</Typography.Text>
            <Typography.Title level={4} style={{ margin: 0 }}>{currency} {total.toFixed(2)}</Typography.Title>
          </div>
        </Card>
      </div>
    </StorefrontLayout>
  );
}
