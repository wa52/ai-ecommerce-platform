"use client";

import { Button, Card, InputNumber, message, Result, Skeleton, Typography } from "antd";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import { checkoutLinesAdd, fetchProductBySlug, type StorefrontProduct } from "@/services/saleor";

function parseDescriptionText(raw: string | null): string {
  if (!raw) return "";
  // Saleor 描述为 EditorJS JSON；sandbox 商品是简单段落
  try {
    const parsed = JSON.parse(raw) as { blocks?: { text?: string }[]; text?: string };
    if (parsed.text) return parsed.text;
    return (parsed.blocks ?? []).map((b) => b.text ?? "").join("\n");
  } catch {
    return raw;
  }
}

export default function ProductDetailPage() {
  const params = useParams<{ slug: string }>();
  const slugString = params?.slug;
  const router = useRouter();
  const [product, setProduct] = useState<StorefrontProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [qty, setQty] = useState(1);
  const [adding, setAdding] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    if (!slugString) return;
    let alive = true;
    fetchProductBySlug(slugString)
      .then((p) => {
        setProduct(p);
        const available = p?.variants.find((v) => (v.quantityAvailable ?? 0) > 0);
        if (p?.price) return;
        void available;
      })
      .catch((e) => messageApi.error(String(e)))
      .finally(() => setLoading(false));
    return () => {
      alive = false;
    };
  }, [slugString, messageApi]);

  async function addToCart(variantId: string) {
    setAdding(true);
    try {
      await checkoutLinesAdd(variantId, qty);
      router.push("/cart");
    } catch (e) {
      messageApi.error(String(e));
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return (
      <StorefrontLayout>
        <Skeleton active paragraph={{ rows: 6 }} />
      </StorefrontLayout>
    );
  }

  if (!product) {
    return (
      <StorefrontLayout>
        <Result status="404" title="商品不存在" />
      </StorefrontLayout>
    );
  }

  const description = parseDescriptionText(product.description);
  const sellableVariants = product.variants.filter((v) => (v.quantityAvailable ?? 0) > 0);
  const variant = sellableVariants[0] ?? product.variants[0] ?? null;
  const price = variant?.price ?? product.price;
  const maxQty = variant?.quantityAvailable ?? 0;

  return (
    <StorefrontLayout>
      {contextHolder}
      <Card>
        <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
          <div
            style={{
              width: 320,
              height: 320,
              background: "#fafafa",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 96,
            }}
          >
            🛍️
          </div>
          <div style={{ flex: 1, minWidth: 320 }}>
            <Typography.Title level={3} style={{ marginTop: 0 }}>
              {product.name}
            </Typography.Title>
            <Typography.Title level={2} style={{ color: "#111", marginTop: 0 }}>
              {price && typeof price.amount === "number" ? `${price.currency} ${price.amount.toFixed(2)}` : "询价"}
            </Typography.Title>
            {variant && (
              <Typography.Paragraph>
                规格库存：{variant.sku ?? variant.name} · 剩余 {maxQty}
              </Typography.Paragraph>
            )}
            {product.isAvailableForPurchase && variant && maxQty > 0 ? (
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <InputNumber min={1} max={maxQty || 1} value={qty} onChange={(v) => setQty(v ?? 1)} />
                <Button type="primary" size="large" loading={adding} onClick={() => addToCart(variant.id)}>
                  加入购物车
                </Button>
              </div>
            ) : (
              <Typography.Text type="danger">暂无库存</Typography.Text>
            )}
            {description && (
              <div style={{ marginTop: 24, whiteSpace: "pre-wrap" }}>
                <Typography.Paragraph strong>商品介绍</Typography.Paragraph>
                <Typography.Paragraph>{description}</Typography.Paragraph>
              </div>
            )}
          </div>
        </div>
      </Card>
    </StorefrontLayout>
  );
}
