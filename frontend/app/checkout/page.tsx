"use client";

import { Button, Card, Checkbox, Form, Input, message, Result, Skeleton, Steps, Typography } from "antd";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import {
  checkoutBillingAddressUpdate,
  checkoutComplete,
  checkoutDeliveryMethodUpdate,
  checkoutEmailUpdate,
  checkoutPaymentCreate,
  checkoutRetrieve,
  checkoutShippingAddressUpdate,
  customerLogin,
  customerRegister,
  getCustomerEmail,
  SALEOR_PAYMENT_GATEWAY,
  SALEOR_PAYMENT_LABEL,
  type Checkout,
} from "@/services/saleor";

interface CheckoutFormValues {
  email: string;
  firstName: string;
  lastName: string;
  streetAddress1: string;
  city: string;
  countryArea: string;
  postalCode: string;
  country: string;
  createAccount: boolean;
}

export default function CheckoutPage() {
  const router = useRouter();
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  const reload = useCallback(
    (opts?: { silent?: boolean }) => {
      if (!opts?.silent) setLoading(true);
      return checkoutRetrieve()
        .then(setCheckout)
        .catch((e) => messageApi.error(String(e)))
        .finally(() => setLoading(false));
    },
    [messageApi]
  );

  useEffect(() => {
    setLoggedIn(Boolean(getCustomerEmail()));
    reload();
  }, [reload]);

  if (loading) {
    return (
      <StorefrontLayout>
        <Skeleton active paragraph={{ rows: 8 }} />
      </StorefrontLayout>
    );
  }

  if (!checkout || checkout.lines.length === 0) {
    return (
      <StorefrontLayout>
        <Result status="info" title="购物车为空" extra={<Button type="primary" onClick={() => router.push("/")}>返回首页</Button>} />
      </StorefrontLayout>
    );
  }

  async function submit(values: CheckoutFormValues) {
    setBusy(true);
    try {
      const addr = {
        firstName: values.firstName,
        lastName: values.lastName,
        streetAddress1: values.streetAddress1,
        city: values.city,
        countryArea: values.countryArea,
        postalCode: values.postalCode,
        country: values.country,
      };
      await checkoutEmailUpdate(values.email);
      await checkoutShippingAddressUpdate(addr);
      await checkoutBillingAddressUpdate(addr);
      if (values.createAccount && !loggedIn) {
        const pwd = `Sf_${Math.random().toString(36).slice(2, 14)}A!`;
        try {
          await customerRegister(values.email, pwd);
        } catch {
          // 已注册账户：直接按新密码登录失败时提示
        }
        await customerLogin(values.email, pwd);
      }
      const afterAddr = await checkoutRetrieve();
      const methods = afterAddr?.shippingMethods ?? [];
      if (methods.length === 0) throw new Error("没有可用的配送方式，请确认收货地址");
      await checkoutDeliveryMethodUpdate(methods[0].id);
      const afterMethod = await checkoutRetrieve();
      const total = afterMethod?.total?.amount ?? 0;
      if (!(total > 0)) throw new Error("订单金额异常");
      await checkoutPaymentCreate(SALEOR_PAYMENT_GATEWAY, total);
      const completed = await checkoutComplete();
      if (completed.order) {
        router.push(`/order/${completed.order.number}`);
      } else {
        throw new Error(completed.error ?? "下单未成功，请重试");
      }
    } catch (e) {
      messageApi.error(String(e));
      await reload({ silent: true });
    } finally {
      setBusy(false);
    }
  }

  const totalAmount = checkout.total?.amount ?? checkout.subtotal?.amount ?? 0;
  const totalLabel = `${checkout.total?.currency ?? checkout.subtotal?.currency ?? "USD"} ${totalAmount.toFixed(2)}`;

  return (
    <StorefrontLayout>
      {contextHolder}
      <Typography.Title level={3}>结算</Typography.Title>
      <Steps current={0} items={[{ title: "收货信息" }, { title: "支付" }, { title: "完成" }]} style={{ maxWidth: 640, marginBottom: 24 }} />
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <Card style={{ flex: 1, minWidth: 360 }}>
          <Form
            layout="vertical"
            onFinish={submit}
            initialValues={{
              country: "US",
              countryArea: "TX",
              firstName: "",
              lastName: "",
              streetAddress1: "",
              city: "",
              postalCode: "",
              email: checkout.email ?? "",
              createAccount: false,
            }}
          >
            <Form.Item name="email" label="邮箱" rules={[{ type: "email", required: true, message: "请输入有效邮箱" }]}>
              <Input placeholder="用于接收订单通知" />
            </Form.Item>
            <div style={{ display: "flex", gap: 12 }}>
              <Form.Item name="firstName" label="名" style={{ flex: 1 }} rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
              <Form.Item name="lastName" label="姓" style={{ flex: 1 }} rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
            </div>
            <Form.Item name="streetAddress1" label="详细地址" rules={[{ required: true, message: "必填" }]}>
              <Input />
            </Form.Item>
            <div style={{ display: "flex", gap: 12 }}>
              <Form.Item name="city" label="城市" style={{ flex: 1 }} rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
              <Form.Item name="countryArea" label="州 / 省" style={{ flex: 1 }} rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
              <Form.Item name="postalCode" label="邮编" style={{ flex: 1 }} rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
              <Form.Item name="country" label="国家" style={{ flex: 0.6 }} rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
            </div>
            {!loggedIn && (
              <Form.Item name="createAccount" valuePropName="checked" extra="下单后自动注册并登录，订单通过邮箱关联账户">
                <Checkbox>同时创建账户并保存订单</Checkbox>
              </Form.Item>
            )}
            <Form.Item>
              <Button type="primary" size="large" htmlType="submit" loading={busy} block>
                下单（{SALEOR_PAYMENT_LABEL}，{totalLabel}）
              </Button>
            </Form.Item>
          </Form>
        </Card>
        <Card style={{ width: 320 }} title="订单摘要">
          {checkout.lines.map((l) => (
            <div key={l.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <Typography.Text>
                {l.variant.name} × {l.quantity}
              </Typography.Text>
              <Typography.Text>
                {l.totalPrice && typeof l.totalPrice.amount === "number" ? `${l.totalPrice.currency} ${l.totalPrice.amount.toFixed(2)}` : "-"}
              </Typography.Text>
            </div>
          ))}
          <div style={{ borderTop: "1px solid #f0f0f0", marginTop: 8, paddingTop: 8, display: "flex", justifyContent: "space-between" }}>
            <Typography.Text strong>合计</Typography.Text>
            <Typography.Text strong>{totalLabel}</Typography.Text>
          </div>
          <div style={{ marginTop: 16 }}>
            <Typography.Text type="secondary">
              {SALEOR_PAYMENT_GATEWAY === "mirumee.payments.dummy"
                ? "当前为沙箱支付：下单即视为支付成功（FULLY_CHARGED）。"
                : "当前使用支付宝支付，支付结果以支付宝异步通知为准。"}
            </Typography.Text>
          </div>
        </Card>
      </div>
    </StorefrontLayout>
  );
}
