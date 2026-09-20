"use client";

import { DeleteOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Skeleton, Typography } from "antd";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import { fetchProductBySlug, getBookCoverFallback, getFavoriteSlugs, toggleFavorite, type StorefrontProduct } from "@/services/saleor";

export default function FavoritesPage() {
  const [products, setProducts] = useState<StorefrontProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    const items = await Promise.all(getFavoriteSlugs().map((slug) => fetchProductBySlug(slug).catch(() => null)));
    setProducts(items.filter((item): item is StorefrontProduct => Boolean(item)));
    setLoading(false);
  }, []);
  useEffect(() => { reload(); }, [reload]);

  return <StorefrontLayout>
    <Typography.Title level={3}>我的收藏</Typography.Title>
    {loading ? <Skeleton active /> : products.length === 0 ? <Empty description="还没有收藏商品"><Link href="/"><Button type="primary">去逛逛</Button></Link></Empty> : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 16 }}>
      {products.map((product) => <Card key={product.id} cover={<Link href={`/product/${product.slug}`}><img src={product.imageUrl ?? getBookCoverFallback(product.slug)} alt={product.name} style={{ aspectRatio: "4 / 5", objectFit: "cover" }} /></Link>} actions={[<Button key="remove" type="text" danger icon={<DeleteOutlined />} onClick={() => { toggleFavorite(product.slug); reload(); }}>取消收藏</Button>]}>
        <Card.Meta title={<Link href={`/product/${product.slug}`}>{product.name}</Link>} description={product.price ? `${product.price.currency} ${product.price.amount.toFixed(2)}` : "询价"} />
      </Card>)}
    </div>}
  </StorefrontLayout>;
}
