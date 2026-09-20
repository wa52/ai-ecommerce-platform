"use client";

import { ShoppingOutlined, UserOutlined } from "@ant-design/icons";
import { Badge, Layout, Menu } from "antd";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { checkoutRetrieve, getCustomerToken } from "@/services/saleor";

const { Header } = Layout;

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [cartQty, setCartQty] = useState(0);
  const [logged, setLogged] = useState(false);

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

  const items = [
    { key: "/", label: <Link href="/">首页</Link> },
    { key: "/cart", label: <Badge size="small" count={cartQty}><span><ShoppingOutlined /> 购物车</span></Badge> },
    {
      key: "/account",
      label: (
        <span>
          <UserOutlined /> {logged ? "我的账户" : "登录 / 注册"}
        </span>
      ),
    },
  ];

  return (
    <Layout style={{ minHeight: "100vh", background: "#fff" }}>
      <Header style={{ background: "#fff", borderBottom: "1px solid #f0f0f0" }}>
        <div style={{ display: "flex", alignItems: "center", maxWidth: 1080, margin: "0 auto", width: "100%" }}>
          <Link href="/" style={{ fontSize: 18, fontWeight: 600, color: "#111", marginRight: 40 }}>
            AI 电商商城
          </Link>
          <Menu
            mode="horizontal"
            selectedKeys={[pathname]}
            items={items}
            style={{ flex: 1, borderBottom: "none", background: "transparent", minWidth: 320 }}
            onClick={(e) => router.push(e.key)}
          />
          <Link href="/admin" style={{ color: "#999", fontSize: 13, marginLeft: 24 }}>
            商家后台
          </Link>
        </div>
      </Header>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "24px 16px 48px", width: "100%" }}>{children}</div>
    </Layout>
  );
}
