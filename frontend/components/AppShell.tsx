"use client";

import { useEffect, useState } from "react";
import { Layout, Menu, Typography } from "antd";
import { LoginPanel, SessionCard, type Session } from "@/features/auth/AuthPanel";
import { fetchMe, getToken, setToken } from "@/services/api";
import SystemStatusPanel from "@/features/system/SystemStatusPanel";
import ProductsPage from "@/features/products/ProductsPage";
import AnalyticsDashboard from "@/features/analytics/AnalyticsDashboard";
import FinancePage from "@/features/finance/FinancePage";

const { Header, Content, Sider } = Layout;

type ViewKey = "system" | "products" | "analytics" | "finance" | "auth";

export default function AppShell() {
  const [view, setView] = useState<ViewKey>("auth");
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    if (!getToken()) return;
    fetchMe()
      .then((me) => setSession({ email: me.email, is_staff: me.is_staff }))
      .catch(() => setToken(null));
  }, []);

  const isAdmin = session?.is_staff === true;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ display: "flex", alignItems: "center" }}>
        <Typography.Title level={4} style={{ color: "#fff", margin: 0 }}>
          AI 跨境电商平台
        </Typography.Title>
      </Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[view]}
            onClick={(e) => setView(e.key as ViewKey)}
            items={[
              { key: "system", label: "系统状态" },
              { key: "products", label: "商品 / 订单" },
              { key: "analytics", label: "数据分析" },
              { key: "finance", label: "财务" },
              { key: "auth", label: session ? "当前用户" : "登录" },
            ]}
          />
        </Sider>
        <Content style={{ padding: 16 }}>
          {view === "system" &&
            (isAdmin ? (
              <SystemStatusPanel />
            ) : (
              <Typography.Paragraph type="warning">请先使用商家账号登录后查看系统状态。</Typography.Paragraph>
            ))}
          {view === "products" &&
            (isAdmin ? (
              <ProductsPage />
            ) : (
              <Typography.Paragraph type="warning">请先使用商家账号登录后再管理商品。</Typography.Paragraph>
            ))}
          {view === "analytics" &&
            (isAdmin ? (
              <AnalyticsDashboard />
            ) : (
              <Typography.Paragraph type="warning">请先使用商家账号登录后查看数据分析。</Typography.Paragraph>
            ))}
          {view === "finance" &&
            (isAdmin ? (
              <FinancePage />
            ) : (
              <Typography.Paragraph type="warning">请先使用商家账号登录后查看财务数据。</Typography.Paragraph>
            ))}
          {view === "auth" &&
            (session ? (
              <SessionCard
                session={session}
                onLogout={() => {
                  setToken(null);
                  setSession(null);
                }}
              />
            ) : (
              <LoginPanel onLogin={setSession} />
            ))}
        </Content>
      </Layout>
    </Layout>
  );
}
