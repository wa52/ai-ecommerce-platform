"use client";

import { useState } from "react";
import { Alert, Button, Card, Form, Input, InputNumber, message, Space, Table, Tag, Typography } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRefund, fetchPayments, fetchRefunds, type FinancePayment, type FinanceRefund } from "@/services/analytics";

export default function AfterSalesPage() {
  const [selected, setSelected] = useState<FinancePayment | null>(null);
  const [form] = Form.useForm<{ amount: number; reason?: string }>();
  const queryClient = useQueryClient();
  const payments = useQuery({ queryKey: ["finance-payments"], queryFn: fetchPayments });
  const refunds = useQuery({ queryKey: ["finance-refunds"], queryFn: fetchRefunds });
  const refund = useMutation({
    mutationFn: (values: { amount: number; reason?: string }) => {
      if (!selected) throw new Error("请选择一笔支付");
      return createRefund({
        payment_id: selected.id,
        amount: values.amount.toFixed(2),
        idempotency_key: `admin-refund-${selected.id}-${Date.now()}`,
        reason: values.reason,
      });
    },
    onSuccess: () => {
      message.success("退款申请已提交");
      form.resetFields();
      setSelected(null);
      void queryClient.invalidateQueries({ queryKey: ["finance-payments"] });
      void queryClient.invalidateQueries({ queryKey: ["finance-refunds"] });
    },
    onError: (error) => message.error(error instanceof Error ? error.message : "退款失败"),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Typography.Title level={3}>售后与退款</Typography.Title>
        <Typography.Paragraph type="secondary">从已支付订单选择支付记录，执行可退款金额内的部分或全额退款。</Typography.Paragraph>
      </div>
      <Alert type="info" showIcon message="当前退款会记入平台财务账本；真实支付宝退款仍需配置支付宝商户密钥并接入异步通知。" />
      <Card title="支付记录">
        <Table<FinancePayment>
          rowKey="id"
          loading={payments.isPending}
          dataSource={payments.data ?? []}
          rowSelection={{ type: "radio", selectedRowKeys: selected ? [selected.id] : [], onChange: (_, rows) => setSelected(rows[0] ?? null) }}
          columns={[
            { title: "订单号", dataIndex: "order_ref" },
            { title: "渠道", dataIndex: "provider" },
            { title: "金额", render: (_, row) => `${row.amount} ${row.currency}` },
            { title: "已退款", render: (_, row) => `${row.refunded_amount} ${row.currency}` },
            { title: "状态", dataIndex: "status", render: (value: string) => <Tag color={value === "paid" ? "green" : "default"}>{value}</Tag> },
          ]}
        />
      </Card>
      <Card title="提交退款" extra={selected ? `订单 ${selected.order_ref}` : "未选择支付记录"}>
        <Form form={form} layout="vertical" onFinish={(values) => refund.mutate(values)} style={{ maxWidth: 520 }}>
          <Form.Item name="amount" label="退款金额" rules={[{ required: true, message: "请输入退款金额" }]}>
            <InputNumber min={0.01} max={selected ? Number(selected.amount) - Number(selected.refunded_amount) : undefined} precision={2} style={{ width: "100%" }} addonAfter={selected?.currency ?? "货币"} disabled={!selected} />
          </Form.Item>
          <Form.Item name="reason" label="退款原因"><Input.TextArea rows={3} maxLength={200} disabled={!selected} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={refund.isPending} disabled={!selected}>提交退款</Button>
        </Form>
      </Card>
      <Card title="售后记录">
        <Table<FinanceRefund>
          rowKey="id"
          loading={refunds.isPending}
          dataSource={refunds.data ?? []}
          columns={[
            { title: "支付 ID", dataIndex: "payment_id" },
            { title: "退款金额", render: (_, row) => `${row.amount} ${row.currency}` },
            { title: "状态", dataIndex: "status" },
            { title: "原因", dataIndex: "reason", render: (value: string | null) => value || "—" },
          ]}
        />
      </Card>
    </Space>
  );
}
