"use client";

import { useQuery } from "@tanstack/react-query";
import { Input, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { fetchOrders, type Order } from "@/services/commerce";

export default function OrdersPage() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["admin-orders", page], queryFn: () => fetchOrders({ page, pageSize: 20 }) });
  return <>
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
    ]} />
  </>;
}
