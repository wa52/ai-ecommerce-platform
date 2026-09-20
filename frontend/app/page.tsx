"use client";

import { Card, Empty, Input, Result, Select, Skeleton, Space, Tag, Typography } from "antd";
import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import StorefrontLayout from "@/components/StorefrontLayout";
import { fetchProducts, getBookCoverFallback, type StorefrontProduct } from "@/services/saleor";
import styles from "./page.module.css";

export default function StorefrontHome() {
  const [products, setProducts] = useState<StorefrontProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [sort, setSort] = useState<string>("default");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    setError(null);
    fetchProducts({ first: 100 })
      .then((page) => setProducts(page.items))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setError(null);
      startTransition(() => {
        fetchProducts({ first: 100, search: search || null })
          .then((page) => setProducts(page.items))
          .catch((e) => setError(String(e)));
      });
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const retry = () => {
    setError(null);
    setProducts(null);
    fetchProducts({ first: 100, search: search || null })
      .then((page) => setProducts(page.items))
      .catch((e) => setError(String(e)));
  };

  const categories = [...new Map((products ?? []).filter((p) => p.category).map((p) => [p.category!.slug, p.category!])).values()];
  const visibleProducts = (products ?? [])
    .filter((p) => category === "all" || p.category?.slug === category)
    .filter((p) => !onlyAvailable || p.isAvailableForPurchase)
    .sort((a, b) => {
      if (sort === "price-asc") return (a.price?.amount ?? Infinity) - (b.price?.amount ?? Infinity);
      if (sort === "price-desc") return (b.price?.amount ?? 0) - (a.price?.amount ?? 0);
      if (sort === "name") return a.name.localeCompare(b.name, "zh-CN");
      return 0;
    });

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
  } else if (visibleProducts.length === 0) {
    content = <Empty description="暂无上架商品" />;
  } else {
    content = (
      <div className={styles.productGrid}>
        {visibleProducts.map((p) => (
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
      <div className={styles.heroRow}>
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
      <div className={styles.filterBar}>
        <Space wrap>
          <Typography.Text type="secondary">分类</Typography.Text>
          <Select value={category} onChange={setCategory} style={{ minWidth: 160 }} options={[{ value: "all", label: "全部分类" }, ...categories.map((c) => ({ value: c.slug, label: c.name }))]} />
          <Typography.Text type="secondary">排序</Typography.Text>
          <Select value={sort} onChange={setSort} style={{ minWidth: 160 }} options={[{ value: "default", label: "推荐排序" }, { value: "price-asc", label: "价格从低到高" }, { value: "price-desc", label: "价格从高到低" }, { value: "name", label: "名称排序" }]} />
          <Tag.CheckableTag checked={onlyAvailable} onChange={setOnlyAvailable}>仅看有货</Tag.CheckableTag>
        </Space>
        {products && <Typography.Text type="secondary">共 {visibleProducts.length} 件商品</Typography.Text>}
      </div>
      {content}
    </StorefrontLayout>
  );
}
