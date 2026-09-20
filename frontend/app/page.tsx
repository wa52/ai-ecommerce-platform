"use client";

import { Card, Empty, Input, Result, Row, Skeleton, Typography } from "antd";
import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import StorefrontLayout from "@/components/StorefrontLayout";
import { fetchProducts, type StorefrontProduct } from "@/services/saleor";

export default function StorefrontHome() {
  const [products, setProducts] = useState<StorefrontProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    fetchProducts({ first: 24 })
      .then((page) => setProducts(page.items))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      startTransition(() => {
        fetchProducts({ first: 24, search: search || null })
          .then((page) => setProducts(page.items))
          .catch((e) => setError(String(e)));
      });
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  let content: React.ReactNode;
  if (error) {
    content = <Result status="warning" title="加载失败" subTitle={error} />;
  } else if (!products) {
    content = (
      <Row gutter={[24, 24]}>
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} style={{ width: 240 }}>
            <Skeleton active paragraph={{ rows: 3 }} />
          </Card>
        ))}
      </Row>
    );
  } else if (products.length === 0) {
    content = <Empty description="暂无上架商品" />;
  } else {
    content = (
      <Row gutter={[24, 24]}>
        {products.map((p) => (
          <Link key={p.id} href={`/product/${p.slug}`} style={{ width: 240 }}>
            <Card
              hoverable
              style={{ width: 240 }}
              cover={<div style={{ height: 170, background: "#fafafa", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 44 }}>🛍️</div>}
            >
              <Card.Meta
                title={p.name}
                description={
                  <Typography.Text strong>
                    {p.price ? `${p.price.currency} ${p.price.amount.toFixed(2)}` : "询价"}
                  </Typography.Text>
                }
              />
            </Card>
          </Link>
        ))}
      </Row>
    );
  }

  return (
    <StorefrontLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          全部商品
        </Typography.Title>
        <Input.Search
          placeholder="搜索商品"
          allowClear
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          loading={pending}
        />
      </div>
      {content}
    </StorefrontLayout>
  );
}
