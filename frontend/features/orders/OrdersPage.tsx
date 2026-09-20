"use client";

import { useQuery } from "@tanstack/react-query";
import { Button, Input, Popconfirm, Table, Tag, Typography, message } from "antd";
import { useState } from "react";
import { cancelOrder, fetchOrders, fulfillOrder, markOrderPaid, type Order } from "@/services/commerce";

export default function OrdersPage() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["admin-orders", page], queryFn: () => fetchOrders({ page, pageSize: 20 }) });
  const [messageApi, contextHolder] = message.useMessage();
  async function run(action: () => Promise<Order>, success: string) { try { await action(); messageApi.success(success); await query.refetch(); } catch (error) { messageApi.error(String(error)); } }
  return <>
    {contextHolder}
    <Typography.Title level={3}>订单管理</Typography.Title>
    <Typography.Paragraph type="secondary">订单数据直接来自 Commerce Core，当前提供分页查看和状态筛选。</Typography.Paragraph>
    <Table<Order> rowKey="id" loading={query.isPending} dataSource={query.data?.items ?? []} pagination={{ current: page, pageSize: 20, total: query.data?.page.total_count ?? 0, onChange: setPage }} columns={[
      { title: "订单号", dataIndex: "number" },
      { title: "状态", dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
      { title: "支付", dataIndex: "payment_status", render: (value: string) => <Tag color={value === "FULLY_CHARGED" ? "success" : "warning"}>{value}</Tag> },
      { title: "渠道", dataIndex: "channel" },
      { title: "金额", render: (_, record) => `${record.total_amount} ${record.currency}` },
      { title: "商品数", render: (_, record) => record.items.reduce((sum, item) => sum + item.quantity, 0) },
      { title: "创建时间", dataIndex: "created_at" },
      { title: "物流", render: (_, record) => record.fulfillments?.map((item) => item.tracking_number || item.status).join("、") || "未发货" },
      { title: "操作", render: (_, record) => <>
        {record.status !== "CANCELED" && <Popconfirm title="确认取消订单？" onConfirm={() => run(() => cancelOrder(record.id), "订单已取消")}><Button danger size="small">取消</Button></Popconfirm>}
        {record.payment_status !== "FULLY_CHARGED" && <Button size="small" style={{ marginLeft: 8 }} onClick={() => run(() => markOrderPaid(record.id), "已标记支付")}>标记支付</Button>}
        {record.status === "UNFULFILLED" && <Button size="small" style={{ marginLeft: 8 }} onClick={() => run(async () => { await fulfillOrder(record.id, record.items.map((item) => ({ orderLineId: item.id, quantity: item.quantity }))); return record; }, "已创建发货单")}>发货</Button>}
      </> },
    ]} />
  </>;
}
