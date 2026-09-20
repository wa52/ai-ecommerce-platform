"use client";

import { CustomerServiceOutlined, FileTextOutlined, RollbackOutlined, SafetyCertificateOutlined, TruckOutlined } from "@ant-design/icons";
import { Button, Card, Collapse, Col, Row, Typography } from "antd";
import StorefrontLayout from "@/components/StorefrontLayout";

const services = [
  { icon: <TruckOutlined />, title: "配送与运费", text: "下单后展示可用配送方式和费用，跨境订单以结算页实时计算为准。" },
  { icon: <RollbackOutlined />, title: "退换货与售后", text: "收到商品后如有质量问题，请保留包装并联系客服，我们会协助处理退换货。" },
  { icon: <SafetyCertificateOutlined />, title: "支付与安全", text: "支付由支付网关处理，商城只保存完成订单所需的信息，不保存支付密钥。" },
  { icon: <FileTextOutlined />, title: "发票说明", text: "需要发票或购买凭证，请在订单备注中说明，并通过客服确认开具信息。" },
  { icon: <CustomerServiceOutlined />, title: "联系客服", text: "工作日 09:00—18:00 提供订单、物流和售后咨询。" },
];

export default function ServicePage() {
  return (
    <StorefrontLayout>
      <section style={{ padding: "12px 0 30px" }}>
        <Typography.Title style={{ marginBottom: 8 }}>服务保障</Typography.Title>
        <Typography.Paragraph type="secondary" style={{ fontSize: 16, maxWidth: 680 }}>
          从下单、支付到收货，我们把常用帮助集中在这里。具体费用和可选项以订单结算页展示为准。
        </Typography.Paragraph>
      </section>
      <Row gutter={[16, 16]}>
        {services.map((service) => (
          <Col xs={24} sm={12} lg={8} key={service.title}>
            <Card style={{ height: "100%" }}>
              <div style={{ fontSize: 28, color: "#1677ff", marginBottom: 12 }}>{service.icon}</div>
              <Typography.Title level={4}>{service.title}</Typography.Title>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>{service.text}</Typography.Paragraph>
            </Card>
          </Col>
        ))}
      </Row>
      <Card title="常见问题" style={{ marginTop: 24 }}>
        <Collapse ghost items={[
          { key: "1", label: "支付成功后在哪里查看订单？", children: "支付完成后会进入订单详情页，也可以在右上角“我的账户”中查看订单历史。" },
          { key: "2", label: "为什么支付页显示沙箱支付？", children: "当前环境用于演示，使用 Saleor Dummy 网关模拟成功支付，不会产生真实扣款。正式上线需要配置支付宝 Payment App 和商户密钥。" },
          { key: "3", label: "订单可以修改收货信息吗？", children: "支付前可以返回结算页修改；支付完成后请尽快联系客服确认是否还能调整。" },
        ]} />
      </Card>
      <Card style={{ marginTop: 24, background: "#f7fbff" }}>
        <Typography.Title level={4}>需要帮助？</Typography.Title>
        <Typography.Paragraph type="secondary">请准备订单号和下单邮箱，我们会更快定位问题。</Typography.Paragraph>
        <Button type="primary" href="mailto:service@example.com">联系在线客服邮箱</Button>
      </Card>
    </StorefrontLayout>
  );
}
