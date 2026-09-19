"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, Col, Row, Table, Tabs, Typography } from "antd";
import { fetchPayments, fetchRefunds, fetchSettlements } from "@/services/analytics";

export default function FinancePage() {
  const payments = useQuery({ queryKey: ["finance-payments"], queryFn: fetchPayments });
  const refunds = useQuery({ queryKey: ["finance-refunds"], queryFn: fetchRefunds });
  const settlements = useQuery({ queryKey: ["finance-settlements"], queryFn: fetchSettlements });

  return (
    <>
      <Typography.Title level={3}>财务</Typography.Title>
      <Tabs
        items={[
          {
            key: "payments",
            label: "Payment",
            children: (
              <Table
                rowKey="id"
                size="small"
                loading={payments.isPending}
                dataSource={payments.data ?? []}
                columns={[
                  { title: "订单", dataIndex: "order_ref" },
                  { title: "渠道", dataIndex: "provider" },
                  { title: "金额", render: (_, r) => `${r.amount} ${r.currency}` },
                  { title: "已退款", render: (_, r) => `${r.refunded_amount} ${r.currency}` },
                  { title: "状态", dataIndex: "status" },
                ]}
              />
            ),
          },
          {
            key: "refunds",
            label: "Refund",
            children: (
              <Table
                rowKey="id"
                size="small"
                loading={refunds.isPending}
                dataSource={refunds.data ?? []}
                columns={[
                  { title: "支付单", dataIndex: "payment_id" },
                  { title: "金额", render: (_, r) => `${r.amount} ${r.currency}` },
                  { title: "原因", dataIndex: "reason" },
                  { title: "状态", dataIndex: "status" },
                ]}
              />
            ),
          },
          {
            key: "settlements",
            label: "Settlement",
            children: (
              <Table
                rowKey="id"
                size="small"
                loading={settlements.isPending}
                dataSource={settlements.data ?? []}
                columns={[
                  { title: "平台", dataIndex: "platform" },
                  { title: "区间", render: (_, r) => `${r.period_start} ~ ${r.period_end}` },
                  { title: "总额", render: (_, r) => `${r.gross_amount} ${r.currency}` },
                  { title: "平台费", dataIndex: "platform_fee" },
                  { title: "支付费", dataIndex: "payment_fee" },
                  { title: "净额", dataIndex: "net_amount" },
                ]}
              />
            ),
          },
        ]}
      />
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card size="small" title="说明">
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              退款上限、幂等与结算手续费由后端 Finance 领域保证；本页仅展示真实数据。
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </>
  );
}
