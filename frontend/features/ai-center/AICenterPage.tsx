"use client";

import { Button, Card, Input, Space, Tabs, Typography, message } from "antd";
import { useState } from "react";
import { request } from "@/services/api";

interface AgentRun { answer?: string; final_answer?: string; output?: string; [key: string]: unknown }

export default function AICenterPage() {
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [productName, setProductName] = useState("");
  const [copy, setCopy] = useState("");
  const [translation, setTranslation] = useState("");
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
  async function generateCopy() {
    setBusy(true); try { const result = await request<{ title?: string; description?: string }>("/ai/copy/product", { method: "POST", body: JSON.stringify({ product_name: productName, features: [] }) }); setCopy(`${result.title ?? ""}\n\n${result.description ?? ""}`); } catch (error) { messageApi.error(String(error)); } finally { setBusy(false); }
  }
  async function translate() {
    setBusy(true); try { const result = await request<{ title?: string; description?: string }>("/ai/translate", { method: "POST", body: JSON.stringify({ title: productName, target_language: "English" }) }); setTranslation(`${result.title ?? ""}\n\n${result.description ?? ""}`); } catch (error) { messageApi.error(String(error)); } finally { setBusy(false); }
  }
  return <>
    {contextHolder}
    <Typography.Title level={3}>AI Center</Typography.Title>
    <Typography.Paragraph type="secondary">Agent 通过真实业务 Tool 查询订单、商品、财务或分析数据；没有数据时不会自动编造结果。</Typography.Paragraph>
    <Tabs items={[
      { key: "agent", label: "运营 Agent", children: <Card title="运营助手"><Space direction="vertical" style={{ width: "100%" }}><Input.TextArea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="例如：查询最近 30 天销售情况" rows={4} /><Button type="primary" onClick={run} loading={busy}>运行 Agent</Button>{answer && <Card size="small" title="结果"><Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{answer}</Typography.Paragraph></Card>}</Space></Card> },
      { key: "copy", label: "商品文案", children: <Card title="AI 商品文案"><Space direction="vertical" style={{ width: "100%" }}><Input value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="输入商品名称" /><Button type="primary" onClick={generateCopy} loading={busy}>生成文案</Button>{copy && <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{copy}</Typography.Paragraph>}</Space></Card> },
      { key: "translate", label: "商品翻译", children: <Card title="AI 商品翻译"><Space direction="vertical" style={{ width: "100%" }}><Input.TextArea value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="输入中文商品标题或描述" rows={4} /><Button type="primary" onClick={translate} loading={busy}>翻译成英文</Button>{translation && <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{translation}</Typography.Paragraph>}</Space></Card> },
    ]} />
  </>;
}
