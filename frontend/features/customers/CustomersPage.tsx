"use client";

import { useQuery } from "@tanstack/react-query";
import { Input, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { fetchCustomers, type Customer } from "@/services/commerce";

export default function CustomersPage() {
  const [page, setPage] = useState(1); const [search, setSearch] = useState("");
  const query = useQuery({ queryKey: ["admin-customers", page, search], queryFn: () => fetchCustomers({ page, pageSize: 20, search }) });
  return <><Typography.Title level={3}>客户管理</Typography.Title><Input.Search placeholder="搜索邮箱或客户" allowClear onSearch={(value) => { setSearch(value); setPage(1); }} style={{ maxWidth: 320, marginBottom: 16 }} /><Table<Customer> rowKey="id" loading={query.isPending} dataSource={query.data?.items ?? []} pagination={{ current: page, pageSize: 20, total: query.data?.page.total_count ?? 0, onChange: setPage }} columns={[{ title: "邮箱", dataIndex: "email" }, { title: "姓名", render: (_, r) => `${r.first_name} ${r.last_name}` }, { title: "订单数", dataIndex: "order_count" }, { title: "状态", render: (_, r) => <Tag color={r.is_active ? "green" : "default"}>{r.is_active ? "正常" : "停用"}</Tag> }, { title: "注册时间", dataIndex: "date_joined" }]} /></>;
}
