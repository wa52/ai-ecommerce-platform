"use client";

import { ArrowRightOutlined, CheckCircleFilled, ClockCircleFilled, CustomerServiceOutlined, GiftFilled, HeartOutlined, SafetyCertificateFilled, SearchOutlined, ThunderboltFilled } from "@ant-design/icons";
import { Card, Empty, Input, Result, Skeleton, Tag } from "antd";
import { useEffect, useMemo, useState, useTransition } from "react";
import Link from "next/link";
import StorefrontLayout from "@/components/StorefrontLayout";
import { fetchProducts, getBookCoverFallback, type StorefrontProduct } from "@/services/saleor";
import styles from "./page.module.css";

const categoryIcons = ["▣", "⌂", "✦", "♧", "⌁", "▤", "♡", "▥", "♧"];
const catalogCategories = [
  ["数码电子", "digital"], ["家居生活", "home"], ["服装鞋包", "fashion"], ["美妆个护", "beauty"],
  ["运动户外", "sports"], ["食品饮料", "food"], ["母婴用品", "baby"], ["图书文创", "books"], ["宠物用品", "pets"],
] as const;

export default function StorefrontHome() {
  const [products, setProducts] = useState<StorefrontProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [pending, startTransition] = useTransition();
  const load = (term = search) => { setError(null); startTransition(() => fetchProducts({ first: 100, search: term || null }).then((page) => setProducts(page.items)).catch((e) => setError(String(e)))); };

  useEffect(() => { load(""); }, []);
  useEffect(() => { const timer = setTimeout(() => load(), 350); return () => clearTimeout(timer); }, [search]);
  useEffect(() => {
    const onHeaderSearch = (event: Event) => { const term = (event as CustomEvent<string>).detail; setSearch(term); load(term); };
    window.addEventListener("sf-home-search", onHeaderSearch);
    return () => window.removeEventListener("sf-home-search", onHeaderSearch);
  }, []);

  const categories = useMemo(() => [...new Map((products ?? []).filter((p) => p.category).map((p) => [p.category!.slug, p.category!])).values()], [products]);
  const knownCategorySlugs = new Set(categories.map((item) => item.slug));
  const visibleProducts = useMemo(() => (products ?? []).filter((p) => category === "all" || !knownCategorySlugs.has(category) || p.category?.slug === category).filter((p) => !onlyAvailable || p.isAvailableForPurchase), [products, category, onlyAvailable, categories]);
  const recommendations = (products ?? []).slice(0, 3);
  const retry = () => { setProducts(null); load(); };

  if (error) return <StorefrontLayout><Result status="warning" title="商品加载失败" subTitle={error} extra={<button onClick={retry}>重新连接</button>} /></StorefrontLayout>;
  return <StorefrontLayout>
    <main className={styles.home}>
      <section className={styles.discoveryGrid}>
        <aside className={styles.categoryPanel}>
          <PanelHeading title="商品分类" action="查看全部" onClick={() => setCategory("all")} />
          <div className={styles.categoryList}>
            {catalogCategories.map(([name, slug], index) => <button key={slug} className={category === slug ? styles.categoryActive : ""} onClick={() => setCategory(slug)}><span>{categoryIcons[index % categoryIcons.length]}</span>{name}</button>)}
            <button onClick={() => setCategory("all")}><span>⊞</span>更多分类</button>
          </div>
          <div className={styles.newcomer}><GiftFilled /><strong>新人专享</strong><span>注册即送 ¥50 优惠券</span><button onClick={() => window.dispatchEvent(new Event("sf-open-auth"))}>立即注册</button></div>
        </aside>
        <div className={styles.heroStack}>
          <section className={styles.heroBanner}><div className={styles.heroCopy}><span className={styles.eyebrow}>AI FOR A BETTER LIFE</span><h1>让 AI 为你的生活<br />发现更多美好</h1><p>精选全球好物 · AI 个性化推荐 · 快速配送 · 售后无忧</p><div className={styles.heroActions}><Link href="#hot">立即选购</Link><Link className={styles.heroGhost} href="/service">了解更多 <ArrowRightOutlined /></Link></div></div><div className={styles.heroOrb}><div className={styles.orbGlow} /><div className={styles.robotFace}><i /><i /></div><div className={styles.robotBody} /></div><div className={styles.chatBubble}>Hi! 👋<br /><strong>我是你的 AI 购物助手</strong><br />有什么可以帮你的吗？</div><div className={styles.heroDots}><b /><b /><b /><b /><b /></div></section>
          <section className={styles.benefits}><Benefit icon={<SafetyCertificateFilled />} title="正品保障" copy="100% 正品保证" /><Benefit icon={<ThunderboltFilled />} title="快速配送" copy="全国包邮 · 次日达" /><Benefit icon={<ClockCircleFilled />} title="7天无理由" copy="售后无忧" /><Benefit icon={<CustomerServiceOutlined />} title="AI 智能推荐" copy="个性化购物体验" /><Benefit icon={<GiftFilled />} title="会员特权" copy="专享优惠福利" /></section>
          <section className={styles.section} id="hot"><div className={styles.sectionTitle}><div><h2>热销商品</h2><div className={styles.tabs}><button className={styles.tabActive}>今日热销</button><button>本周热销</button><button>本月热销</button></div></div><Link href="#all-products">查看更多 <ArrowRightOutlined /></Link></div><div className={styles.productGrid}>{!products ? [0, 1, 2, 3, 4, 5].map((i) => <Card key={i} className={styles.productCard}><Skeleton active paragraph={{ rows: 3 }} /></Card>) : visibleProducts.slice(0, 6).map((p, index) => <ProductCard key={p.id} product={p} index={index} />)}</div>{products && !visibleProducts.length && <Empty description="暂无匹配商品" />}</section>
        </div>
        <aside className={styles.recommendPanel}><PanelHeading title="今日推荐" action="换一换" onClick={() => load("")} />{recommendations.map((p) => <Link href={`/product/${p.slug}`} key={p.id} className={styles.recommendItem}><img src={p.imageUrl ?? getBookCoverFallback(p.slug)} alt={p.name} /><span><strong>{p.name}</strong><small>{p.description?.slice(0, 18) || "精选好物推荐"}</small><em>{p.price ? `¥${p.price.amount.toFixed(0)}` : "查看详情"}</em></span></Link>)}<Link className={styles.aiTile} href="/service"><span>AI 导购</span><small>为你推荐最适合的商品</small><b>开始对话 <ArrowRightOutlined /></b><div className={styles.miniRobot}>●●</div></Link></aside>
      </section>
      <section className={styles.promoGrid}><Promo className={styles.promoBlue} title="数字好物" copy="探索科技的无限可能" /><Promo className={styles.promoGreen} title="品质生活" copy="让家更温暖" /><Promo className={styles.promoWarm} title="时尚穿搭" copy="发现更美的自己" /></section>
      <section className={styles.toolbar} id="all-products"><div><span className={styles.eyebrowDark}>EXPLORE THE COLLECTION</span><h2>全部商品</h2></div><div className={styles.toolbarControls}><Input.Search placeholder="搜索商品" value={search} onChange={(e) => setSearch(e.target.value)} onSearch={(v) => load(v)} loading={pending} enterButton={<SearchOutlined />} /><button className={onlyAvailable ? styles.stockOn : ""} onClick={() => setOnlyAvailable((v) => !v)}>仅看有货</button></div></section><div className={styles.productGrid}>{visibleProducts.map((p, index) => <ProductCard key={p.id} product={p} index={index} />)}</div>
    </main>
  </StorefrontLayout>;
}

function PanelHeading({ title, action, onClick }: { title: string; action: string; onClick: () => void }) { return <div className={styles.panelHeading}><h2>{title}</h2><button onClick={onClick}>{action}</button></div>; }
function ProductCard({ product, index }: { product: StorefrontProduct; index: number }) { return <Link href={`/product/${product.slug}`} className={styles.productLink}><article className={styles.productCard}><div className={styles.productImage}>{index < 2 && <Tag color={index === 0 ? "red" : "green"}>{index === 0 ? "热销" : "新品"}</Tag>}<img src={product.imageUrl ?? getBookCoverFallback(product.slug)} alt={product.imageAlt ?? product.name} onError={(event) => { event.currentTarget.src = getBookCoverFallback(product.slug); }} /><button aria-label="收藏" onClick={(event) => event.preventDefault()}><HeartOutlined /></button></div><div className={styles.productInfo}><strong>{product.name}</strong><small>{product.description?.replace(/<[^>]+>/g, "").slice(0, 22) || "精选好物 · AI 智能推荐"}</small><div className={styles.price}>{product.price ? `¥${product.price.amount.toFixed(0)}` : "询价"}<del>{product.price ? `¥${(product.price.amount * 1.2).toFixed(0)}` : ""}</del></div><div className={styles.rating}>★ 4.9 <span>1.2k+ 已售</span></div></div></article></Link>; }
function Benefit({ icon, title, copy }: { icon: React.ReactNode; title: string; copy: string }) { return <div className={styles.benefit}><span>{icon}</span><div><strong>{title}</strong><small>{copy}</small></div></div>; }
function Promo({ className, title, copy }: { className: string; title: string; copy: string }) { return <div className={`${styles.promo} ${className}`}><h3>{title}</h3><p>{copy}</p><Link href="#hot">立即选购 <ArrowRightOutlined /></Link><div className={styles.promoShape} /></div>; }
