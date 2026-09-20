"use client";

import { Button, Card, Result } from "antd";
import { useRouter } from "next/navigation";
import StorefrontLayout from "@/components/StorefrontLayout";

export default function AlipayReturnPage() {
  const router = useRouter();
  return (
    <StorefrontLayout>
      <Card>
        <Result
          status="info"
          title="支付宝已返回"
          subTitle="支付结果正在由服务器异步确认，请稍后到我的订单查看。"
          extra={[
            <Button type="primary" key="account" onClick={() => router.push("/account")}>
              查看我的订单
            </Button>,
            <Button key="home" onClick={() => router.push("/")}>继续购物</Button>,
          ]}
        />
      </Card>
    </StorefrontLayout>
  );
}
