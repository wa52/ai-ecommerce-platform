"use client";

import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Typography } from "antd";
import { fetchInventory, type Stock } from "@/services/commerce";

export default function InventoryPage() {
  const query = useQuery({ queryKey: ["admin-inventory"], queryFn: () => fetchInventory({ page: 1, pageSize: 100 }) });
  return <>
    <Typography.Title level={3}>库存管理</Typography.Title>
    <Typography.Paragraph type="secondary">显示 Saleor 仓库库存和 SKU，库存调整通过 Commerce API 执行并保留流水。</Typography.Paragraph>
    <Table<Stock> rowKey={(record) => `${record.variant_id}-${record.warehouse_id}`} loading={query.isPending} dataSource={query.data?.items ?? []} pagination={false} columns={[
      { title: "SKU", dataIndex: "sku" },
      { title: "仓库", dataIndex: "warehouse_name" },
      { title: "数量", dataIndex: "quantity", render: (value: number) => <Tag color={value > 0 ? "green" : "red"}>{value}</Tag> },
    ]} />
  </>;
}
