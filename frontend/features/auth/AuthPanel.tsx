"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Card, Descriptions, Form, Input, Spin, Tag, Typography, message } from "antd";
import { fetchMe, login, setToken } from "@/services/api";

export interface Session {
  email: string;
  is_staff: boolean;
}

export function LoginPanel({ onLogin }: { onLogin: (session: Session) => void }) {
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (values: { email: string; password: string }) => {
      const result = await login(values.email, values.password);
      setToken(result.token);
      const me = await fetchMe();
      return me;
    },
    onSuccess: (me) => {
      message.success(`欢迎，${me.email}`);
      onLogin({ email: me.email, is_staff: me.is_staff });
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <Card title="登录（身份由 Saleor 提供）" style={{ maxWidth: 420 }}>
      {error && <Alert type="error" showIcon message="登录失败" description={error} style={{ marginBottom: 16 }} />}
      <Form layout="vertical" onFinish={(v) => mutation.mutate(v)}>
        <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email", message: "请输入合法邮箱" }]}>
          <Input autoComplete="username" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={mutation.isPending} block>
          登录
        </Button>
      </Form>
    </Card>
  );
}

export function SessionCard({ session, onLogout }: { session: Session; onLogout: () => void }) {
  return (
    <Card title="当前用户" style={{ maxWidth: 420 }}>
      <Descriptions column={1} size="small">
        <Descriptions.Item label="邮箱">{session.email}</Descriptions.Item>
        <Descriptions.Item label="角色">
          <Tag color={session.is_staff ? "gold" : "blue"}>{session.is_staff ? "管理员" : "普通用户"}</Tag>
        </Descriptions.Item>
      </Descriptions>
      <Button onClick={onLogout} style={{ marginTop: 12 }}>
        退出登录
      </Button>
    </Card>
  );
}

export function Loading() {
  return (
    <Spin tip="加载中…">
      <div style={{ minHeight: 120 }} />
    </Spin>
  );
}

export function ErrorBox({ message: text }: { message: string }) {
  return <Alert type="error" showIcon message="出错了" description={text} />;
}

export function PageTitle({ children }: { children: React.ReactNode }) {
  return <Typography.Title level={3}>{children}</Typography.Title>;
}
