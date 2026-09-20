"use client";

import { Button, Card, Input, Space, Typography, message } from "antd";
import { useState } from "react";
import { request } from "@/services/api";

interface AgentRun { answer?: string; final_answer?: string; output?: string; [key: string]: unknown }

export default function AICenterPage() {
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  async function run() {
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      const result = await request<AgentRun>("/agent/run", { method: "POST", body: JSON.stringify({ agent: "operations", prompt }) });
      setAnswer(String(result.answer ?? result.final_answer ?? result.output ?? JSON.stringify(result, null, 2)));
    } catch (error) { messageApi.error(String(error)); }
    finally { setBusy(false); }
  }
  return <>
    {contextHolder}
    <Typography.Title level={3}>AI Center</Typography.Title>
    <Typography.Paragraph type="secondary">Agent 通过真实业务 Tool 查询订单、商品、财务或分析数据；没有数据时不会自动编造结果。</Typography.Paragraph>
    <Card title="运营助手">
      <Space direction="vertical" style={{ width: "100%" }}>
        <Input.TextArea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="例如：查询最近 30 天销售情况" rows={4} />
        <Button type="primary" onClick={run} loading={busy}>运行 Agent</Button>
        {answer && <Card size="small" title="结果"><Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{answer}</Typography.Paragraph></Card>}
      </Space>
    </Card>
  </>;
}
