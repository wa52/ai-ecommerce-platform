"use client";

import { SearchOutlined, ShoppingOutlined, UserOutlined } from "@ant-design/icons";
import { Badge, Button, Form, Input, Layout, Modal, Tabs, message } from "antd";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { checkoutRetrieve, customerLogin, customerRegister, getCustomerToken } from "@/services/saleor";
import styles from "./StorefrontLayout.module.css";

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

  return (
    <Layout className={styles.layout}>
      {contextHolder}
      <Header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark}>▣</span><span className={styles.brandText}>AI 电商商城<small>生活更美好 · AI 更懂你</small></span>
          </Link>
          <nav className={styles.nav} aria-label="主导航">
            <Link className={pathname === "/" ? styles.active : ""} href="/">首页</Link>
            <Link href="/#all-products">全部商品</Link><Link href="/#hot">热销榜单</Link><Link href="/service">服务保障</Link>
          </nav>
          <div className={styles.search}><Input.Search value={headerSearch} onChange={(e) => setHeaderSearch(e.target.value)} onSearch={(value) => { window.dispatchEvent(new CustomEvent("sf-home-search", { detail: value })); router.push("/"); }} placeholder="搜索商品、品牌或关键词..." enterButton={<SearchOutlined />} /></div>
          <button className={styles.language}>◎ 中文⌄</button>
          {logged ? (
            <button className={styles.account} onClick={() => router.push("/account")}><UserOutlined /><span>我的账户<small>账户中心</small></span></button>
          ) : (
            <button className={styles.account} onClick={() => { setAuthMode("login"); setAuthOpen(true); }}><UserOutlined /><span>我的账户<small>登录 / 注册</small></span></button>
          )}
          <Link className={styles.cart} href="/cart"><Badge count={cartQty} size="small"><ShoppingOutlined /></Badge><span>购物车</span></Link>
        </div>
      </Header>
      <div className={styles.content}>{children}</div>
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
