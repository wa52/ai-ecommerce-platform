"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Descriptions, Radio, Row, Space, Statistic, Table, Tag, Typography } from "antd";
import { fetchFormulas, fetchOverview } from "@/services/analytics";

const METRIC_LABELS: Record<string, string> = {
  gmv: "GMV",
  net_sales: "销售额",
  order_count: "订单量",
  avg_order_value: "客单价",
  refund_total: "退款总额",
  refund_rate_percent: "退款率(%)",
  platform_fee: "平台手续费",
  payment_fee: "支付手续费",
  net_settled: "实际到账",
  other_cost: "其他成本",
  profit: "利润",
  profit_margin_percent: "利润率(%)",
};

export default function AnalyticsDashboard() {
  const [days, setDays] = useState(30);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["analytics", days],
    queryFn: () => fetchOverview(days),
  });
  const formulas = useQuery({ queryKey: ["analytics-formulas"], queryFn: fetchFormulas });

  const currencies = Object.keys(data?.by_currency ?? {});

  return (
    <>
      <Typography.Title level={3}>数据分析</Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <span>时间范围：</span>
        <Radio.Group value={days} onChange={(e) => setDays(e.target.value)}>
          <Radio.Button value={1}>今日</Radio.Button>
          <Radio.Button value={7}>7 天</Radio.Button>
          <Radio.Button value={30}>30 天</Radio.Button>
        </Radio.Group>
      </Space>

      {isError && (
        <Alert type="error" showIcon message="加载失败" description={error.message} style={{ marginBottom: 16 }} />
      )}
      {data?.note && <Alert type="info" showIcon message={data.note} style={{ marginBottom: 16 }} />}

      <Row gutter={[16, 16]}>
        {currencies.map((cur) => {
          const m = data!.by_currency[cur];
          return (
            <Col xs={24} xl={12} key={cur}>
              <Card title={`${cur} 指标（近 ${days} 天）`} loading={isPending}>
                <Row gutter={[16, 16]}>
                  {["gmv", "net_sales", "profit", "profit_margin_percent"].map((key) => (
                    <Col span={12} key={key}>
                      <Statistic
                        title={METRIC_LABELS[key]}
                        value={m[key as keyof typeof m]}
                        suffix={key.endsWith("percent") ? "%" : cur}
                      />
                    </Col>
                  ))}
                </Row>
                <Descriptions bordered size="small" column={2} style={{ marginTop: 16 }}>
                  {["order_count", "avg_order_value", "refund_total", "refund_rate_percent", "platform_fee", "payment_fee", "net_settled", "other_cost"].map(
                    (key) => (
                      <Descriptions.Item key={key} label={METRIC_LABELS[key]}>
                        {m[key as keyof typeof m]}
                      </Descriptions.Item>
                    )
                  )}
                </Descriptions>
              </Card>
            </Col>
          );
        })}
      </Row>

      <Card title="指标口径（唯一定义，避免前后端/AI 口径不一致）" style={{ marginTop: 24 }}>
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          loading={formulas.isPending}
          dataSource={Object.entries(formulas.data ?? {}).map(([key, value]) => ({
            key,
            name: METRIC_LABELS[key] ?? key,
            formula: value,
          }))}
          columns={[
            { title: "指标", dataIndex: "name", width: 160 },
            { title: "公式", dataIndex: "formula" },
          ]}
        />
      </Card>

      {isPending && <Tag color="blue" style={{ marginTop: 16 }}>加载中…</Tag>}
    </>
  );
}
