"use client";

import { SearchOutlined, ShoppingOutlined, UserOutlined } from "@ant-design/icons";
import { Badge, Button, Form, Input, Layout, Menu, Modal, Tabs, message } from "antd";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { checkoutRetrieve, customerLogin, customerRegister, getCustomerToken } from "@/services/saleor";

const { Header } = Layout;

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [cartQty, setCartQty] = useState(0);
  const [logged, setLogged] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authBusy, setAuthBusy] = useState(false);
  const [headerSearch, setHeaderSearch] = useState("");
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    let alive = true;
    const refresh = () => {
      if (!alive) return;
      setLogged(Boolean(getCustomerToken()));
      checkoutRetrieve()
        .then((c) => {
          if (alive) setCartQty((c?.lines ?? []).reduce((s, l) => s + l.quantity, 0));
        })
        .catch(() => undefined);
    };
    refresh();
    window.addEventListener("sf-cart-changed", refresh);
    return () => {
      alive = false;
      window.removeEventListener("sf-cart-changed", refresh);
    };
  }, [pathname]);

  useEffect(() => {
    const openAuth = () => {
      setAuthMode("login");
      setAuthOpen(true);
    };
    window.addEventListener("sf-open-auth", openAuth);
    return () => window.removeEventListener("sf-open-auth", openAuth);
  }, []);

  async function handleLogin(values: { email: string; password: string }) {
    setAuthBusy(true);
    try {
      await customerLogin(values.email, values.password);
      setLogged(true);
      setAuthOpen(false);
      messageApi.success("登录成功");
      router.refresh();
    } catch (error) {
      messageApi.error(String(error));
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleRegister(values: { email: string; password: string }) {
    setAuthBusy(true);
    try {
      await customerRegister(values.email, values.password);
      messageApi.success("注册成功，请登录");
      setAuthMode("login");
    } catch (error) {
      messageApi.error(String(error));
    } finally {
      setAuthBusy(false);
    }
  }

  const items = [
    { key: "/", label: <Link href="/">首页</Link> },
    { key: "/#all-products", label: <Link href="/#all-products">全部商品</Link> },
    { key: "/#hot", label: <Link href="/#hot">热销榜单</Link> },
    { key: "/service", label: <Link href="/service">服务保障</Link> },
    { key: "/cart", label: <Badge size="small" count={cartQty}><span><ShoppingOutlined /> 购物车</span></Badge> },
  ];

  return (
    <Layout style={{ minHeight: "100vh", background: "#fff" }}>
      {contextHolder}
      <Header style={{ background: "#fff", borderBottom: "1px solid #edf0f5", height: 72, lineHeight: "72px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, maxWidth: 1440, margin: "0 auto", width: "100%" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 205, fontSize: 19, fontWeight: 750, color: "#17233f" }}>
            <span style={{ display: "grid", placeItems: "center", width: 34, height: 34, borderRadius: 10, color: "#fff", background: "linear-gradient(135deg,#475cff,#7187ff)", fontSize: 20 }}>▣</span>
            <span>AI 电商商城<small style={{ display: "block", marginTop: -19, color: "#8993a8", fontSize: 8, fontWeight: 400, letterSpacing: 1 }}>生活更美好 · AI 更懂你</small></span>
          </Link>
          <Menu
            mode="horizontal"
            selectedKeys={[pathname]}
            items={items}
            style={{ flex: 1, borderBottom: "none", background: "transparent", minWidth: 360 }}
            onClick={(e) => router.push(e.key.split("#")[0] || "/")}
          />
          <Input.Search value={headerSearch} onChange={(e) => setHeaderSearch(e.target.value)} onSearch={(value) => { window.dispatchEvent(new CustomEvent("sf-home-search", { detail: value })); router.push("/"); }} placeholder="搜索商品、品牌或关键词..." enterButton={<SearchOutlined />} style={{ width: 300 }} />
          {logged ? (
            <Button type="text" icon={<UserOutlined />} onClick={() => router.push("/account")}>
              我的账户
            </Button>
          ) : (
            <Button type="link" onClick={() => { setAuthMode("login"); setAuthOpen(true); }}>
              登录 / 注册
            </Button>
          )}
        </div>
      </Header>
      <div style={{ maxWidth: 1440, margin: "0 auto", padding: "18px 24px 48px", width: "100%" }}>{children}</div>
      <Modal
        open={authOpen}
        title={authMode === "login" ? "登录账户" : "创建账户"}
        footer={null}
        centered
        destroyOnClose
        onCancel={() => setAuthOpen(false)}
      >
        <Tabs
          activeKey={authMode}
          onChange={(key) => setAuthMode(key as "login" | "register")}
          items={[
            {
              key: "login",
              label: "登录",
              children: (
                <Form layout="vertical" onFinish={handleLogin} preserve={false}>
                  <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}>
                    <Input placeholder="name@example.com" size="large" />
                  </Form.Item>
                  <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
                    <Input.Password size="large" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={authBusy} block size="large">登录</Button>
                </Form>
              ),
            },
            {
              key: "register",
              label: "注册",
              children: (
                <Form layout="vertical" onFinish={handleRegister} preserve={false}>
                  <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}>
                    <Input placeholder="name@example.com" size="large" />
                  </Form.Item>
                  <Form.Item name="password" label="密码" rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}>
                    <Input.Password size="large" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={authBusy} block size="large">创建账户</Button>
                </Form>
              ),
            },
          ]}
        />
      </Modal>
    </Layout>
  );
}
