"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { createTask, fetchHealth, fetchTaskStatus } from "@/services/api";
import type { TaskStatus } from "@/types/api";

const CheckTag = ({ ok, label }: { ok: boolean; label: string }) => (
  <Tag color={ok ? "green" : "red"}>{label}：{ok ? "正常" : "异常"}</Tag>
);

export default function Home() {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15000,
  });

  const [task, setTask] = useState<TaskStatus | null>(null);
  const taskMutation = useMutation({
    mutationFn: async () => {
      const created = await createTask("ping", { from: "storefront" });
      for (let i = 0; i < 20; i++) {
        const st = await fetchTaskStatus(created.id);
        if (st.status !== "queued") return st;
        await new Promise((r) => setTimeout(r, 500));
      }
      return { id: created.id, task: created.name, status: "failed" as const, error: "轮询超时" };
    },
    onSuccess: setTask,
    onError: (e) => message.error(e.message),
  });

  return (
    <main style={{ padding: 24 }}>
      <Typography.Title level={3}>AI 跨境电商平台 — 系统状态</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="运行健康检查（实时调用后端 /api/v1/health）">
            {isPending ? (
              <Spin tip="加载中…"><div style={{ minHeight: 120 }} /></Spin>
            ) : isError ? (
              <Alert
                type="error"
                showIcon
                message="无法连接 AI 后端"
                description={error.message}
                action={<Button onClick={() => refetch()}>重试</Button>}
              />
            ) : (
              <>
                <Space wrap style={{ marginBottom: 16 }}>
                  <CheckTag ok={data!.postgres.ok} label="PostgreSQL" />
                  <CheckTag ok={data!.redis.ok} label="Redis" />
                  <CheckTag ok={data!.saleor.ok} label="Saleor" />
                  <Tag color={data!.status === "ok" ? "green" : "orange"}>总体：{data!.status}</Tag>
                </Space>
                <Descriptions bordered size="small" column={1}>
                  {([data!.postgres, data!.redis, data!.saleor] as const).map((c) => (
                    <Descriptions.Item key={c.name} label={c.name}>
                      {c.ok ? c.detail : <Typography.Text type="danger">{c.detail}</Typography.Text>}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              </>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Worker 任务闭环（创建 → 执行 → 查询结果）">
            <Button
              type="primary"
              loading={taskMutation.isPending}
              onClick={() => taskMutation.mutate()}
            >
              执行 ping 任务
            </Button>
            {task && (
              <Descriptions bordered size="small" column={1} style={{ marginTop: 16 }}>
                <Descriptions.Item label="任务 ID">{task.id}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={task.status === "success" ? "green" : "red"}>{task.status}</Tag>
                </Descriptions.Item>
                {task.result && (
                  <Descriptions.Item label="结果">
                    {JSON.stringify(task.result)}
                  </Descriptions.Item>
                )}
                {task.error && (
                  <Descriptions.Item label="错误">
                    <Typography.Text type="danger">{task.error}</Typography.Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            )}
          </Card>
        </Col>
      </Row>
    </main>
  );
}
