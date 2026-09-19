import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Input, Modal, Popconfirm, Space, Table, Tag, Typography, message } from "antd";
import { useState } from "react";
import {
  createProduct,
  deleteProduct,
  fetchOrders,
  fetchProducts,
  type Product,
} from "@/services/commerce";

export default function ProductsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const qc = useQueryClient();
  const pageSize = 10;

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["products", page, search],
    queryFn: () => fetchProducts({ page, pageSize, search }),
  });

  const orders = useQuery({ queryKey: ["orders"], queryFn: () => fetchOrders({ page: 1, pageSize: 5 }) });

  const createMutation = useMutation({
    mutationFn: createProduct,
    onSuccess: () => {
      message.success("商品已创建");
      setModalOpen(false);
      form.resetFields();
      qc.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProduct,
    onSuccess: () => {
      message.success("商品已删除");
      qc.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (e: Error) => message.error(e.message),
  });

  return (
    <main style={{ padding: 24 }}>
      <Typography.Title level={3}>商品管理</Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索商品"
          allowClear
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
          style={{ width: 260 }}
        />
        <Button type="primary" onClick={() => setModalOpen(true)}>
          新建商品
        </Button>
        <Button onClick={() => refetch()}>刷新</Button>
      </Space>

      {isError && (
        <Typography.Paragraph type="danger">
          加载失败：{error.message}（请先登录并确认后端可用）
        </Typography.Paragraph>
      )}

      <Table<Product>
        rowKey="id"
        loading={isPending}
        dataSource={data?.items ?? []}
        pagination={{
          current: page,
          pageSize,
          total: data?.page.total_count ?? 0,
          onChange: setPage,
          showSizeChanger: false,
        }}
        columns={[
          { title: "名称", dataIndex: "name" },
          { title: "Slug", dataIndex: "slug" },
          { title: "类型", dataIndex: "product_type" },
          {
            title: "渠道",
            dataIndex: "channels",
            render: (channels: string[]) => channels.map((c) => <Tag key={c}>{c}</Tag>),
          },
          {
            title: "操作",
            render: (_, record) => (
              <Popconfirm title="确认删除该商品？" onConfirm={() => deleteMutation.mutate(record.id)}>
                <Button danger size="small" loading={deleteMutation.isPending}>
                  删除
                </Button>
              </Popconfirm>
            ),
          },
        ]}
      />

      <Card title="最近订单" style={{ marginTop: 24 }}>
        <Table
          rowKey="id"
          size="small"
          loading={orders.isPending}
          dataSource={orders.data?.items ?? []}
          pagination={false}
          columns={[
            { title: "订单号", dataIndex: "number" },
            { title: "状态", dataIndex: "status" },
            { title: "支付", dataIndex: "payment_status" },
            { title: "金额", render: (_, r) => `${r.total_amount} ${r.currency}` },
            { title: "条目", render: (_, r) => r.items.length },
          ]}
        />
      </Card>

      <Modal
        title="新建商品"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => createMutation.mutate(v)}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="slug"
            label="Slug"
            rules={[{ required: true, pattern: /^[a-z0-9-]+$/, message: "仅小写字母、数字和连字符" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </main>
  );
}
