"use client";

import { Card, Empty, Input, Result, Skeleton, Typography } from "antd";
import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import StorefrontLayout from "@/components/StorefrontLayout";
import { fetchProducts, getBookCoverFallback, type StorefrontProduct } from "@/services/saleor";
import styles from "./page.module.css";

export default function StorefrontHome() {
  const [products, setProducts] = useState<StorefrontProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    setError(null);
    fetchProducts({ first: 24 })
      .then((page) => setProducts(page.items))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setError(null);
      startTransition(() => {
        fetchProducts({ first: 24, search: search || null })
          .then((page) => setProducts(page.items))
          .catch((e) => setError(String(e)));
      });
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const retry = () => {
    setError(null);
    setProducts(null);
    fetchProducts({ first: 24, search: search || null })
      .then((page) => setProducts(page.items))
      .catch((e) => setError(String(e)));
  };

  let content: React.ReactNode;
  if (error) {
    content = (
      <Result
        status="warning"
        title="商品加载失败"
        subTitle={error}
        extra={<button onClick={retry} style={{ padding: "8px 18px", cursor: "pointer" }}>重新连接</button>}
      />
    );
  } else if (!products) {
    content = (
      <div className={styles.productGrid}>
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className={styles.productCard}>
            <Skeleton active paragraph={{ rows: 3 }} />
          </Card>
        ))}
      </div>
    );
  } else if (products.length === 0) {
    content = <Empty description="暂无上架商品" />;
  } else {
    content = (
      <div className={styles.productGrid}>
        {products.map((p) => (
          <Link key={p.id} href={`/product/${p.slug}`} className={styles.productLink}>
            <Card
              hoverable
              className={styles.productCard}
              cover={<img
                src={p.imageUrl ?? getBookCoverFallback(p.slug)}
                alt={p.imageAlt ?? p.name}
                className={styles.cover}
                onError={(event) => {
                  const fallback = getBookCoverFallback(p.slug);
                  if (event.currentTarget.src.endsWith(fallback)) return;
                  event.currentTarget.src = fallback;
                }}
              />}
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
      </div>
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
