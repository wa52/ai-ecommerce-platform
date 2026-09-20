# AGENTS.md — AI 跨境电商平台

AI-Native 跨境电商：**Saleor 3.23 = Commerce Core**，**FastAPI = AI 扩展层**，**Next.js 16 = Storefront + Admin**（架构见 `PROJECT_SPEC.md` §2.1）。模块化单体；AI 层不得复制 Saleor 业务模型，也不得直写 Saleor 数据库。

## Git / 提交（最容易踩坑）

- 本项目**不是独立 git 仓库**，位于 `D:\AiProjects` umbrella 仓库内。项目目录内跑 `git` 相关命令是错的；先 `cd D:\AiProjects` 再从 umbrella 操作，且 `git status` 会有几百条无关项目的噪音，**忽略它们**。
- 提交并推送到 GitHub 一律走：`powershell -File scripts\push_github.ps1 -Message "feat(xxx): 中文摘要"`（内部用 `git subtree split` 抽取本项目历史）。**不要**手动 `git add -A` / `git commit -a`。
- 提交风格：`feat(storefront): ...` / `chore(engineering): ...`，消息用中文。

## 架构落点

```
Next.js (3000) ── NEXT_PUBLIC_SALEOR_API_URL ──> Saleor GraphQL (8000)  ← Storefront 直连
        │──────── NEXT_PUBLIC_AI_API_URL ─────> FastAPI (8001)         ← Admin 走 AI 层
Saleor(8000) → PostgreSQL(saleor 库) + Celery Worker + Dashboard(9000)
FastAPI(8001) → PostgreSQL(ai_platform 库) + Redis + MinIO
```

- **两个 API 基址、两种身份**：Storefront（消费者）直接调 Saleor GraphQL（匿名可浏览/下单；客户用 Saleor `accountRegister`/`tokenCreate`）；Admin（商家）调 FastAPI（IAM 也是代理 Saleor `tokenCreate`）。登录态各自独立存 localStorage（`sf_customer_token` vs `ai_platform_token`）。
- **Storefront 页面与 Admin 分离**：`frontend/app/` 根目录即商城（`/product/[slug]` `/cart` `/checkout` `/order/[number]` `/account`）；管理后台在 `frontend/app/admin/`（组件 `AppShell`）。改动 Admin 不要破坏商城，反之亦然。
- **Saleor 金额是 TaxedMoney 形状 `{gross:{amount,currency}}`**，前端 `services/saleor.ts` 的 `normalizeCheckout` 已归一为 `{amount,currency}`。新增取价字段必须走归一化。
- **匿名商品列表可见性**：Saleor `ProductChannelListing.visible_in_listings` 默认 false，只 `isPublished` 不会出现在匿名 `products` 查询里。`backend/app/modules/commerce/application/service.py` 的 `publish_to_channel` 已设置 `visibleInListings: true`——改这里时别丢。`stocks` 字段要 staff 权限，Storefront 用 `quantityAvailable`。
- **数据库三个**：`ecommerce`（AI 层默认）、`saleor`、`ai_platform`。`db/init/create-databases.sh` 只在卷首次初始化时建后两者。

## 开发命令

```powershell
# 后端单测（121 个，asyncio_mode=auto）
cd backend; .venv\Scripts\python -m pytest
# 前端 typecheck + 构建（Windows 上 Turbopack 原生绑定坏，build 必须用 --webpack，package.json 已固化）
cd frontend; npx tsc --noEmit; npm run build
# 前端容器重建（改前端后必须 --build 否则镜像不更新；`docker compose up -d` 单独跑不会重建）
docker compose up -d --build frontend
# AI 层迁移
docker compose exec ai-backend alembic upgrade head
# Storefront 前置初始化（幂等）：关注册邮箱确认 + 补商品 Listing 可见性
powershell -File scripts\saleor_storefront_init.ps1
# Saleor 管理员（验收脚本依赖）：首次创建或重置密码
docker compose exec saleor-api python3 manage.py createsuperuser --email admin@example.com
```

## 验收脚本（`backend/scripts/*_acceptance.py`）

- 真实调用运行中的栈（PostgreSQL/Saleor），凭据全从环境变量读，**不硬编码**。常用：`IAM_ADMIN_EMAIL` / `IAM_ADMIN_PASSWORD` / `IAM_CUSTOMER_EMAIL` / `IAM_CUSTOMER_PASSWORD`（IAM/commerce/ai/agent/rag/analytics/finance…）、`SALEOR_ADMIN_EMAIL` / `SALEOR_ADMIN_PASSWORD`（saleor/storefront）。
- 沙箱集成是内嵌 fake server（在脚本内自起 HTTP 线程）：Fake LLM 默认 `host.docker.internal:9098`、Fake Shopify 默认 `host.docker.internal:9099`；支付用 Saleor 内置 Dummy 网关（`mirumee.payments.dummy`，下单即 FULLY_CHARGED）。
- `storefront_acceptance.py` 跑消费者完整 E2E（匿名列表→checkout→下单→客户订单历史）。
- **真实第三方均 BLOCKED/NOT_VERIFIED**（缺外部凭据）：不要声称真实 Shopify/Stripe/LLM/Embedding 已验证。

## 文档约定

- 证据落盘 `docs/evidence/<phase>/`（验收报告引用），新验收项要留可复查输出。
- `ACCEPTANCE_REPORT.md` 顶部有「PASS 语义说明」：PASS=该阶段内部实现通过，**不是最终产品完成**；真实集成单独标 BLOCKED。改动报告别把这两类混同。
- UI 文案用中文，协议/格式名保持英文（YOLO、GraphQL、Saleor…）。
- `.env` 在 `.gitignore`，凭据不入库；必填项缺失时 compose 启动直接报错（这是设计行为）。

## 环境注意

- 本机 Docker Hub 域名被 DNS 污染（`auth.docker.io` / `registry-1.docker.io` 解析到错误 IP）。拉基础镜像用镜像源 `docker pull docker.m.daocloud.io/library/node:22-alpine` 再 `docker tag` 成本地名；前端 build 失败先怀疑网络不是代码。