"use client";

import { useEffect, useState } from "react";
import { Layout, Menu, Typography } from "antd";
import { LoginPanel, SessionCard, type Session } from "@/features/auth/AuthPanel";
import { fetchMe, getToken, setToken } from "@/services/api";
import SystemStatusPanel from "@/features/system/SystemStatusPanel";
import ProductsPage from "@/features/products/ProductsPage";
import AnalyticsDashboard from "@/features/analytics/AnalyticsDashboard";
import FinancePage from "@/features/finance/FinancePage";
import OrdersPage from "@/features/orders/OrdersPage";
import InventoryPage from "@/features/inventory/InventoryPage";
import AICenterPage from "@/features/ai-center/AICenterPage";
import CustomersPage from "@/features/customers/CustomersPage";
import CategoriesPage from "@/features/categories/CategoriesPage";
import AfterSalesPage from "@/features/after-sales/AfterSalesPage";

const { Header, Content, Sider } = Layout;

type ViewKey = "system" | "products" | "categories" | "orders" | "inventory" | "customers" | "analytics" | "finance" | "after-sales" | "ai" | "auth";

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
              { key: "categories", label: "分类管理" },
              { key: "orders", label: "订单管理" },
              { key: "inventory", label: "库存管理" },
              { key: "customers", label: "客户管理" },
              { key: "analytics", label: "数据分析" },
              { key: "finance", label: "财务" },
              { key: "after-sales", label: "售后 / 退款" },
              { key: "ai", label: "AI Center" },
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
          {view === "orders" &&
            (isAdmin ? <OrdersPage /> : <Typography.Paragraph type="warning">请先使用商家账号登录后管理订单。</Typography.Paragraph>)}
          {view === "categories" &&
            (isAdmin ? <CategoriesPage /> : <Typography.Paragraph type="warning">请先使用商家账号登录后管理分类。</Typography.Paragraph>)}
          {view === "inventory" &&
            (isAdmin ? <InventoryPage /> : <Typography.Paragraph type="warning">请先使用商家账号登录后管理库存。</Typography.Paragraph>)}
          {view === "customers" &&
            (isAdmin ? <CustomersPage /> : <Typography.Paragraph type="warning">请先使用商家账号登录后管理客户。</Typography.Paragraph>)}
          {view === "ai" &&
            (isAdmin ? <AICenterPage /> : <Typography.Paragraph type="warning">请先使用商家账号登录后使用 AI Center。</Typography.Paragraph>)}
          {view === "finance" &&
            (isAdmin ? (
              <FinancePage />
            ) : (
              <Typography.Paragraph type="warning">请先使用商家账号登录后查看财务数据。</Typography.Paragraph>
            ))}
          {view === "after-sales" &&
            (isAdmin ? <AfterSalesPage /> : <Typography.Paragraph type="warning">请先使用商家账号登录后处理售后。</Typography.Paragraph>)}
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
