"use client";

import { useQuery } from "@tanstack/react-query";
import { Table, Typography } from "antd";
import { fetchCategories, type Category } from "@/services/commerce";

export default function CategoriesPage() {
  const query = useQuery({ queryKey: ["admin-categories"], queryFn: fetchCategories });
  return <><Typography.Title level={3}>分类管理</Typography.Title><Typography.Paragraph type="secondary">商品分类来自 Saleor Commerce Core，商城筛选直接使用同一份分类数据。</Typography.Paragraph><Table<Category> rowKey="id" loading={query.isPending} dataSource={query.data?.items ?? []} pagination={false} columns={[{ title: "名称", dataIndex: "name" }, { title: "Slug", dataIndex: "slug" }, { title: "层级", dataIndex: "level" }]} /></>;
}
