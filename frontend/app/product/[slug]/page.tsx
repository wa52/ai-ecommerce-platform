"use client";

import { Button, Card, Divider, InputNumber, message, Result, Skeleton, Tag, Typography } from "antd";
import { HeartOutlined, HeartFilled } from "@ant-design/icons";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import { checkoutLinesAdd, fetchProductBySlug, getBookCoverFallback, isFavorite, toggleFavorite, type StorefrontProduct } from "@/services/saleor";

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
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [favorite, setFavorite] = useState(false);
  const [adding, setAdding] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    if (!slugString) return;
    let alive = true;
    fetchProductBySlug(slugString)
      .then((p) => {
        setProduct(p);
        if (p) setFavorite(isFavorite(p.slug));
        setSelectedVariantId(p?.variants.find((v) => (v.quantityAvailable ?? 0) > 0)?.id ?? p?.variants[0]?.id ?? null);
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
  const variant = product.variants.find((item) => item.id === selectedVariantId) ?? sellableVariants[0] ?? product.variants[0] ?? null;
  const price = variant?.price ?? product.price;
  const maxQty = variant?.quantityAvailable ?? 0;

  return (
    <StorefrontLayout>
      {contextHolder}
      <Card>
        <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
          <div style={{ width: 320, maxWidth: "100%" }}>
            <img
              src={product.imageUrl ?? getBookCoverFallback(product.slug)}
              alt={product.imageAlt ?? product.name}
              style={{ width: "100%", aspectRatio: "4 / 5", objectFit: "cover", borderRadius: 8 }}
              onError={(event) => {
                const fallback = getBookCoverFallback(product.slug);
                if (event.currentTarget.src.endsWith(fallback)) return;
                event.currentTarget.src = fallback;
              }}
            />
            {product.media.length > 1 && (
              <div style={{ display: "flex", gap: 8, marginTop: 10, overflowX: "auto" }}>
                {product.media.map((media, index) => (
                  <img key={`${media.url}-${index}`} src={media.url} alt={media.alt ?? `${product.name} 图片 ${index + 1}`} style={{ width: 56, height: 70, objectFit: "cover", borderRadius: 4, border: index === 0 ? "2px solid #1677ff" : "1px solid #eee" }} />
                ))}
              </div>
            )}
          </div>
          <div style={{ flex: 1, minWidth: 320 }}>
            <Typography.Title level={3} style={{ marginTop: 0 }}>
              {product.name} <Button type="text" icon={favorite ? <HeartFilled style={{ color: "#ff4d4f" }} /> : <HeartOutlined />} onClick={() => setFavorite(toggleFavorite(product.slug))}>{favorite ? "已收藏" : "收藏"}</Button>
            </Typography.Title>
            <Typography.Title level={2} style={{ color: "#111", marginTop: 0 }}>
              {price && typeof price.amount === "number" ? `${price.currency} ${price.amount.toFixed(2)}` : "询价"}
            </Typography.Title>
            {product.category && <Tag color="blue">{product.category.name}</Tag>}
            {product.variants.length > 1 && (
              <div style={{ margin: "20px 0" }}>
                <Typography.Text strong>选择规格</Typography.Text>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                  {product.variants.map((item) => (
                    <Button key={item.id} type={item.id === variant?.id ? "primary" : "default"} disabled={(item.quantityAvailable ?? 0) <= 0} onClick={() => { setSelectedVariantId(item.id); setQty(1); }}>
                      {item.name}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            {variant && (
              <Typography.Paragraph>
                规格库存：{variant.sku ?? variant.name} · {maxQty > 0 ? `剩余 ${maxQty}` : "暂时缺货"}
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
                <Divider />
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
