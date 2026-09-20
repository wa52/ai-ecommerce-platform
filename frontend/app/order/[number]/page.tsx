"use client";

import { Button, Card, Descriptions, Tag, Typography } from "antd";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import { getLastOrder, type StorefrontOrder } from "@/services/saleor";

export default function OrderConfirmationPage() {
  const params = useParams<{ number: string }>();
  const router = useRouter();
  const [order, setOrder] = useState<StorefrontOrder | null>(null);

  useEffect(() => {
    const last = getLastOrder();
    if (last && (!params?.number || last.number === params.number)) {
      setOrder(last);
    }
  }, [params?.number]);

  if (!order) {
    return (
      <StorefrontLayout>
        <Card>
          <Typography.Title level={3}>订单 {params?.number}</Typography.Title>
          <Typography.Paragraph type="secondary">
            订单已提交。登录后可在「我的账户 → 我的订单」查看订单详情。
          </Typography.Paragraph>
          <Button type="primary" onClick={() => router.push("/account")}>
            登录查看订单
          </Button>
        </Card>
      </StorefrontLayout>
    );
  }

  return (
    <StorefrontLayout>
      <Card>
        <Typography.Title level={2} style={{ color: "#52c41a", marginTop: 0 }}>
          ✔ 下单成功
        </Typography.Title>
        {params?.number && params.number !== order.number && (
          <Typography.Paragraph type="warning">正在显示最近一笔订单（#{order.number}）。</Typography.Paragraph>
        )}
        <Descriptions column={2} style={{ marginBottom: 24 }}>
          <Descriptions.Item label="订单号">#{order.number}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color="processing">{order.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="支付状态">
            <Tag color="success">{order.paymentStatus}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="下单时间">{order.created}</Descriptions.Item>
        </Descriptions>
        <Typography.Title level={4}>明细</Typography.Title>
        {order.lines.map((l, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f0f0f0" }}>
            <Typography.Text>
              {l.variantName} × {l.quantity}
            </Typography.Text>
            <Typography.Text>
              {l.unitPrice && typeof l.unitPrice.amount === "number" ? `${l.unitPrice.currency} ${l.unitPrice.amount.toFixed(2)}` : "-"}
            </Typography.Text>
          </div>
        ))}
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <Typography.Text strong>
            合计：{order.total && typeof order.total.amount === "number" ? `${order.total.currency} ${order.total.amount.toFixed(2)}` : "-"}
          </Typography.Text>
        </div>
        {order.fulfillments.length > 0 && <>
          <Typography.Title level={4} style={{ marginTop: 24 }}>物流信息</Typography.Title>
          {order.fulfillments.map((fulfillment) => <Card size="small" key={fulfillment.id} style={{ marginBottom: 8 }}>
            <Tag color="processing">{fulfillment.status}</Tag> {fulfillment.trackingNumber || "待分配运单号"}
          </Card>)}
        </>}
        <Button style={{ marginTop: 24 }} type="primary" onClick={() => router.push("/account")}>
          我的订单
        </Button>
      </Card>
    </StorefrontLayout>
  );
}
