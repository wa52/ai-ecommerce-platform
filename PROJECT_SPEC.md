# AI 跨境电商管理平台 --- PROJECT_SPEC

## 1. 项目定位

构建一个面向商家独立电商网站场景的 **AI 全栈电商平台**：既包含消费者 Storefront，也包含商家 Admin，并保留未来扩展跨境、多渠道和多店铺能力。

系统统一管理多个跨境电商平台和多个店铺，并提供：

-   商品管理
-   订单管理
-   库存管理
-   多店铺管理
-   收付款
-   退款
-   结算
-   财务对账
-   数据分析
-   AI 商品分析
-   AI 商品文案
-   AI 翻译
-   AI Agent
-   RAG 知识库
-   第三方电商平台接入

支持的平台采用插件化设计，包括但不限于
Amazon、Shopify、Shopee、Lazada、TikTok Shop 和其他平台。

第一阶段采用 **模块化单体（Modular
Monolith）**，不采用微服务，但所有业务模块必须保持清晰边界，使未来可以逐步拆分成独立服务。

------------------------------------------------------------------------


## 2.1 开发框架与电商底座（新增）

本项目不从零实现通用电商基础能力，采用 **成熟电商框架 + AI 扩展层** 的方式开发。

### 项目业务形态

系统按“**一个商家搭建并运营自己的电商网站**”设计，同时保留未来扩展多店铺、多渠道销售的能力。

系统包含两个主要使用端：

1. **消费者商城（Storefront）**
   - 首页
   - 商品分类
   - 商品详情
   - 搜索
   - 购物车
   - 结账
   - 支付
   - 用户账户
   - 我的订单
   - 退款/售后

2. **商家管理后台（Admin）**
   - 商品管理
   - SKU / Variant
   - 分类
   - 价格
   - 库存
   - 订单
   - 客户
   - 优惠/促销
   - 支付与退款
   - 履约/物流
   - 财务与数据分析
   - AI Center

### 推荐技术底座

V1 优先采用：

```text
Storefront
Next.js + TypeScript
        │
        ▼
Commerce Core
Saleor（成熟 Headless 电商框架）
        │
        ├── 商品
        ├── SKU / Variant
        ├── Cart / Checkout
        ├── Order
        ├── Customer
        ├── Promotion
        ├── Payment
        ├── Inventory
        └── Fulfillment
        │
        ▼
PostgreSQL
```

AI 与企业扩展能力独立于 Commerce Core：

```text
                 ┌──────────────────────┐
                 │      Next.js         │
                 │ Storefront + Admin   │
                 └──────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │     Commerce Core     │
                │        Saleor         │
                └───────────┬───────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
      PostgreSQL       Payment/物流       Integration
                                                │
                                                ▼
                                      Amazon/Shopify/...（后续）

                ┌───────────────────────────────┐
                │       AI Extension Layer      │
                │ Python + FastAPI              │
                ├───────────────────────────────┤
                │ LLM Gateway                   │
                │ Agent Runtime                 │
                │ RAG                           │
                │ Product AI                    │
                │ Translation                   │
                │ Analytics AI                  │
                └───────────────────────────────┘
```

### 框架职责边界

**Saleor 负责成熟电商能力，不重复造轮子：**

- Product / Variant
- Category / Collection
- Customer
- Cart / Checkout
- Order
- Inventory
- Promotion
- Payment
- Refund
- Fulfillment
- 基础 Admin 能力

**FastAPI 负责 AI 与自定义扩展：**

- LLM Gateway
- Agent
- RAG
- AI 商品标题/描述
- AI 翻译
- AI 商品分析
- AI 运营助手
- 自定义数据分析
- 后续平台 Connector

业务代码禁止复制一套 Saleor 已经提供的商品、订单、库存、Checkout 核心模型。

### 为什么采用这种方式

项目重点不再是让 AI 从零生成一个购物车、订单、支付和库存系统，而是：

```text
成熟 Commerce Core
        +
现代 Storefront
        +
商家运营后台
        +
AI / Agent / RAG
        +
后续多渠道 Connector
```

这样既是一个真正可运行的电商网站，也能体现 AI 全栈开发能力。

### 可替换性要求

Commerce Core 必须通过 API / Adapter 与 AI 和扩展模块通信。

禁止：

```text
AI Module
   ↓
直接依赖 Saleor 内部数据库表
```

推荐：

```text
AI Module
   ↓
Commerce Adapter
   ↓
Saleor API
```

因此未来若更换 Commerce Framework，AI、RAG、Agent 和大部分自定义业务模块无需整体重写。


## 2. 总体架构

``` text
Frontend
Next.js + TypeScript + Ant Design
        │
        │ REST API / SSE
        ▼
FastAPI Backend
        │
        ├── IAM：用户 / 登录 / 权限
        ├── Commerce：商品 / 订单 / 库存
        ├── Store：多店铺管理
        ├── Finance：支付 / 退款 / 结算 / 对账
        ├── Analytics：数据分析
        ├── AI：Agent / RAG / LLM / Tools
        └── Connector System
                ├── Amazon
                ├── Shopify
                ├── Shopee
                ├── Lazada
                └── Payment
        │
        ├── PostgreSQL + pgvector
        ├── Redis
        └── Worker
              ├── AI Task
              ├── Order Sync
              ├── Product Sync
              ├── Translation
              └── Reconciliation
```

------------------------------------------------------------------------

## 3. 技术栈

### Frontend

-   Next.js
-   TypeScript
-   Ant Design
-   TanStack Query

负责页面、表格、Dashboard、表单、数据展示、Agent UI、流式 AI
输出和用户操作。

### Backend

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy 2
-   Alembic

采用 **Modular Monolith + Domain Modules**。所有核心业务运行在一个
Backend 中，第一阶段禁止拆微服务。

### Data & Infrastructure

-   PostgreSQL：核心业务数据库
-   pgvector：RAG 向量数据
-   Redis：缓存、任务队列、任务状态
-   MinIO / S3 Compatible Storage：文件和商品素材
-   Worker：异步任务
-   Docker Compose：V1 部署

------------------------------------------------------------------------

## 4. Backend Modules

``` text
backend/
├── modules/
│   ├── iam/
│   ├── commerce/
│   ├── store/
│   ├── finance/
│   ├── analytics/
│   └── ai/
├── connectors/
├── infrastructure/
├── api/
└── main.py
```

每个核心业务模块内部建议继续分为：

``` text
module/
├── api/
├── application/
├── domain/
└── repository/
```

API 层不能直接承载核心业务逻辑。

------------------------------------------------------------------------

## 5. IAM

负责：

-   用户
-   登录
-   注册
-   JWT
-   Role
-   Permission
-   RBAC
-   API Key
-   审计

核心对象：

-   User
-   Role
-   Permission
-   UserRole
-   RolePermission

------------------------------------------------------------------------

## 6. Commerce

负责：

-   Product
-   Product Variant
-   Order
-   Order Item
-   Inventory
-   Inventory Log

主要能力：

-   商品 CRUD
-   SKU 管理
-   商品状态
-   订单管理
-   订单状态
-   库存管理
-   库存变化记录
-   商品搜索
-   订单搜索

------------------------------------------------------------------------

## 7. Store

负责多平台、多店铺管理。

示例：

``` text
Amazon Store A
Amazon Store B
Shopify Store A
Shopee Store A
Shopee Store B
```

统一 Store 模型至少包含：

``` text
id
name
platform
status
currency
country
credentials
created_at
updated_at
```

敏感 Credential 不允许明文保存。

------------------------------------------------------------------------

## 8. Connector Plugin System

所有第三方电商平台必须通过 Connector 接入。

禁止：

``` text
Commerce -> Amazon API
```

必须：

``` text
Commerce
   ↓
Connector Interface
   ↓
AmazonConnector
```

统一接口示例：

``` python
class EcommerceConnector:
    async def get_products(self):
        ...

    async def get_orders(self):
        ...

    async def get_inventory(self):
        ...

    async def create_product(self, product):
        ...

    async def update_product(self, product):
        ...

    async def update_inventory(self, inventory):
        ...
```

实现可包括：

-   AmazonConnector
-   ShopifyConnector
-   ShopeeConnector
-   LazadaConnector
-   TikTokShopConnector

------------------------------------------------------------------------

## 9. 数据标准化

外部平台的数据结构不能直接进入核心 Domain。

AmazonOrder、ShopifyOrder、ShopeeOrder 等平台数据必须经过 Connector
转换为内部统一模型，例如 `UnifiedOrder`。

``` text
UnifiedOrder
├── id
├── external_id
├── platform
├── store_id
├── items
├── amount
├── currency
├── payment_status
├── order_status
├── created_at
└── updated_at
```

核心业务只能依赖内部统一模型。

------------------------------------------------------------------------

## 10. Finance

Finance 必须作为独立 Domain，不能只在 Order 上增加 `paid = true`。

核心对象：

-   Payment
-   PaymentTransaction
-   Refund
-   RefundTransaction
-   Settlement
-   SettlementItem
-   Reconciliation
-   FinanceLedger

支持：

-   支付
-   收款
-   退款
-   部分退款
-   结算
-   平台手续费
-   支付手续费
-   对账
-   多币种
-   汇率
-   利润计算

------------------------------------------------------------------------

## 11. Payment Connector

支付系统同样采用 Connector。

``` text
Finance
   ↓
Payment Interface
   ↓
Payment Connector
```

未来可实现：

-   StripeConnector
-   PayPalConnector
-   PlatformPaymentConnector

支付相关必须考虑：

-   Webhook 验签
-   Idempotency
-   Decimal / 最小货币单位金额处理
-   Transaction Log
-   Audit Log
-   Secret Management

禁止使用浮点数直接处理货币金额。

------------------------------------------------------------------------

## 12. Analytics

负责：

-   销售额
-   GMV
-   订单量
-   客单价
-   退款率
-   库存
-   实际到账
-   平台手续费
-   支付手续费
-   利润
-   商品利润
-   店铺利润
-   平台利润
-   趋势分析

Dashboard 支持 Today、7 Days、30 Days 和自定义时间范围。

------------------------------------------------------------------------

## 13. AI Core

AI 是 Backend 中的一个独立 Domain，而不是整个系统架构。

``` text
backend/modules/ai/
├── agent/
├── llm/
├── rag/
├── tools/
├── workflow/
├── prompts/
└── memory/
```

------------------------------------------------------------------------

## 14. LLM Gateway

所有模型调用必须经过统一的 `LLMGateway`。

禁止业务模块直接依赖某个具体模型厂商 API。

``` text
Business
   ↓
LLMGateway
   ↓
Provider
```

Provider 可以包括：

-   OpenAIProvider
-   AnthropicProvider
-   GeminiProvider
-   OpenAICompatibleProvider

未来增加模型时优先增加 Provider，而不是修改所有 AI 调用代码。

------------------------------------------------------------------------

## 15. Agent Runtime

Agent 不能写死数量和角色。

``` text
Agent Registry
       │
       ├── Agent A
       ├── Agent B
       └── Agent N
```

Agent 通过 Capability 获取能力：

``` text
Agent
  ↓
Capability Registry
  ├── RAG
  ├── Product
  ├── Order
  ├── Finance
  ├── Analytics
  ├── Translation
  └── External Tools
```

新增 AI 能力时优先新增 Tool / Capability，而不是不断修改 Agent Runtime。

------------------------------------------------------------------------

## 16. RAG

RAG 只是 Agent 可以调用的一种能力，不作为整个 AI 系统的中心。

``` text
Agent
   ↓
RAG Tool
   ↓
Retriever
   ↓
Hybrid Retrieval
   ↓
Vector + Keyword
   ↓
Rerank
   ↓
Context
```

核心数据：

-   KnowledgeBase
-   Document
-   DocumentChunk
-   Embedding

向量存储使用 pgvector。

------------------------------------------------------------------------

## 17. AI 电商能力

V1 至少考虑：

-   AI 商品描述生成
-   AI 标题生成
-   AI 商品翻译
-   AI 商品卖点生成
-   AI 商品分析
-   AI 订单分析
-   AI 财务分析

例如：

``` text
用户：
“分析这个月利润为什么下降”

Agent
 ↓
Finance Tool
 ↓
Analytics Tool
 ↓
Order Tool
 ↓
Database
 ↓
LLM
 ↓
分析结果
```

------------------------------------------------------------------------

## 18. Worker

耗时任务不能长期阻塞 HTTP 请求。

使用 Redis + Worker 执行：

-   Amazon 订单同步
-   Shopify 商品同步
-   库存同步
-   批量翻译
-   AI 长任务
-   RAG Embedding
-   财务对账
-   数据统计

``` text
Frontend
   ↓
FastAPI
   ↓
Create Task
   ↓
Redis Queue
   ↓
Worker
   ↓
Execute
   ↓
Database
```

Worker 可以和 FastAPI 共用 Domain、Repository、Connector
和数据库模型，它仍然属于模块化单体体系，不等于业务微服务化。

------------------------------------------------------------------------

## 19. Frontend Structure

``` text
frontend/
├── app/
├── components/
├── features/
│   ├── auth/
│   ├── products/
│   ├── orders/
│   ├── inventory/
│   ├── stores/
│   ├── finance/
│   ├── analytics/
│   └── ai/
├── services/
├── hooks/
├── types/
└── utils/
```

------------------------------------------------------------------------

## 20. 前端页面

``` text
Dashboard

商品管理
├── 商品列表
├── 商品详情
├── 商品编辑
└── AI生成

订单管理
├── 订单列表
└── 订单详情

库存管理

店铺管理
├── 店铺列表
└── 添加店铺

财务
├── Payment
├── Refund
├── Settlement
├── Reconciliation
└── Profit

数据分析

AI Center
├── AI Assistant
├── 商品文案
├── 商品翻译
├── 商品分析
└── 知识库

系统管理
├── 用户
├── Role
├── Permission
└── Settings
```

------------------------------------------------------------------------

## 21. Database Core

初步核心表：

``` text
users
roles
permissions

stores
platform_accounts

products
product_variants
platform_products

orders
order_items

inventory
inventory_logs

payments
payment_transactions

refunds
refund_transactions

settlements
settlement_items

finance_ledger

ai_tasks
agent_runs

conversations
messages

knowledge_bases
documents
document_chunks
```

实际开发时通过 Alembic 管理数据库 Migration。

------------------------------------------------------------------------

## 22. Infrastructure

``` text
infrastructure/
├── database/
├── redis/
├── storage/
├── queue/
├── logging/
├── security/
└── config/
```

------------------------------------------------------------------------

## 23. Docker

V1 使用 Docker Compose。

运行组件：

``` text
Frontend
Backend
Worker
PostgreSQL
Redis
MinIO
```

V1 不引入 Kubernetes。

------------------------------------------------------------------------

## 24. 完整运行结构

``` text
                         USER
                          │
                          ▼
                 ┌─────────────────┐
                 │     Next.js     │
                 │    Frontend     │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │     FastAPI     │
                 │     Backend     │
                 └────────┬────────┘
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
      Commerce         Finance             AI
          │               │                │
          │               │         Agent / RAG
          │               │                │
          └───────────────┼────────────────┘
                          │
                          ▼
                    PostgreSQL
                    + pgvector
                          │
                    Redis / Queue
                          │
                          ▼
                        Worker
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
       Amazon          Shopify           Shopee
                          │
                          ▼
                 Payment / LLM Providers
```

------------------------------------------------------------------------

## 25. 架构原则

整个项目遵循：

-   High Cohesion
-   Low Coupling
-   模块边界清晰
-   Domain 不依赖第三方平台
-   第三方平台通过 Connector
-   AI 能力通过 Capability
-   LLM 通过 Gateway
-   耗时任务通过 Worker
-   数据库访问通过 Repository
-   API 不直接写核心业务逻辑

特别禁止出现：

``` text
Controller
    ↓
一个超大 Service
    ↓
大量 if platform == amazon
    ↓
直接调用各种 AI API
    ↓
直接 SQL
```

------------------------------------------------------------------------

## 26. 不过度设计

V1 明确不使用：

-   Microservices
-   Kubernetes
-   Kafka
-   Service Discovery
-   Distributed Transaction
-   复杂 Event Sourcing

除非以后出现真实业务需求。

------------------------------------------------------------------------

## 27. 未来微服务拆分能力

虽然 V1 是模块化单体，但
IAM、Commerce、Finance、AI、Connector、Analytics 之间必须保持清晰边界。

未来有真实需求时可以逐步拆分：

``` text
Modular Monolith
        ↓
Commerce Service
Finance Service
AI Service
Connector Worker
Analytics Service
```

V1 不进行拆分。

------------------------------------------------------------------------

## 28. V1 开发顺序

### Phase 1 --- 基础骨架

``` text
项目骨架
↓
Frontend + Backend
↓
Docker
↓
PostgreSQL
↓
Redis
```

### Phase 2 --- IAM

``` text
登录
↓
用户
↓
RBAC
```

### Phase 3 --- 电商核心

``` text
Store
↓
Product
↓
Order
↓
Inventory
```

### Phase 4 --- 平台接入

``` text
Connector Interface
↓
选择一个真实平台
↓
真实同步商品/订单
```

### Phase 5 --- Finance

``` text
Payment
↓
Refund
↓
Settlement
↓
Reconciliation
```

### Phase 6 --- 基础 AI

``` text
LLM Gateway
↓
AI 商品文案
↓
AI 翻译
```

### Phase 7 --- Agent

``` text
Agent Runtime
↓
Tool Registry
↓
Commerce Tool
↓
Finance Tool
↓
Analytics Tool
```

### Phase 8 --- RAG

``` text
Knowledge Base
↓
Document / Chunk
↓
Retrieval
↓
Agent RAG Tool
```

### Phase 9 --- Analytics

``` text
Dashboard
↓
销售分析
↓
利润分析
```

### Phase 10 --- 工程化

``` text
Tests
↓
Security
↓
Logging
↓
Docker Deployment
```

### Phase 11 --- 消费者 Storefront

``` text
匿名浏览商品
↓
商品详情 / Variant
↓
购物车（Saleor Checkout）
↓
收货 / 账单地址
↓
配送方式
↓
支付
↓
下单完成
↓
客户注册 / 登录
↓
订单历史
```

Storefront 直接调用 Saleor GraphQL；FastAPI 继续只承担 AI 扩展层和商家后台能力，
不在 AI 层复制商品、购物车、订单或支付核心模型。

------------------------------------------------------------------------

## 29. V1 完成标准

至少完成以下业务闭环：

``` text
用户登录
   ↓
添加店铺
   ↓
连接第三方平台
   ↓
同步商品
   ↓
同步订单
   ↓
查看库存
   ↓
查看支付状态
   ↓
退款 / 结算数据
   ↓
查看销售和利润
   ↓
使用 AI 分析
```

AI 至少能够支持类似：

-   "分析最近 30 天销售情况"
-   "哪些商品利润下降？"
-   "生成这个商品的英文商品描述"
-   "把商品信息翻译成日语"
-   "分析退款率突然升高的原因"

消费者购买闭环也必须可用：

``` text
匿名浏览商品
   ↓
商品详情与 Variant
   ↓
购物车
   ↓
结算 / 地址 / 配送
   ↓
支付并完成订单
   ↓
客户账户 / 订单历史
```

------------------------------------------------------------------------

## 30. 测试要求

至少包含：

-   Unit Test
-   API Test
-   Repository Test
-   Connector Test
-   Finance Test
-   Agent Tool Test

支付、退款、库存重点测试：

-   重复请求
-   并发
-   幂等
-   异常
-   超时
-   第三方 API 失败
-   数据一致性与回滚

------------------------------------------------------------------------

## 31. AI 编程规则

使用 Codex / Claude Code / OpenCode 等 AI 编程工具时：

**禁止 AI 自行修改总体架构。**

开发流程：

``` text
读取 PROJECT_SPEC.md
↓
确定当前 Module
↓
检查已有 Interface
↓
实现功能
↓
编写 Test
↓
运行 Test
↓
检查模块边界
↓
提交 Git
```

新增第三方平台：

``` text
优先新增 Connector
```

而不是污染 Commerce Core。

新增 AI 能力：

``` text
优先新增 Tool / Capability
```

而不是修改 Agent Runtime 核心。

新增模型：

``` text
新增 LLM Provider
```

而不是修改所有 AI 调用代码。

------------------------------------------------------------------------

## 32. Git 与交付

每个阶段完成并通过测试后提交 Git。

建议 Commit 保持小而清晰，例如：

``` text
feat(iam): add RBAC authentication
feat(commerce): add product management
feat(connectors): add Shopify connector
feat(finance): add payment transaction model
feat(ai): add LLM gateway
feat(agent): add capability registry
test(finance): add refund idempotency tests
```

主分支必须保持可运行。

------------------------------------------------------------------------

## 33. 项目最终定位

项目不是普通电商网站，也不是单纯的 Agent Demo。

项目定位：

> **AI-Native Multi-Platform E-Commerce Management Platform**

即：

``` text
传统业务系统
+
多平台 Connector
+
统一数据模型
+
财务系统
+
数据分析
+
Agent
+
RAG
+
AI Automation
```

第一阶段重点不是追求功能数量，而是确保：

**前端能用、后端清晰、数据库正规、业务能跑、Connector 可扩展、AI
可插拔、测试能兜底。**

---

# 34. 项目验收规范（Acceptance Criteria）

## 34.1 Definition of Done（统一完成定义）

任何功能只有同时满足以下条件，才允许标记为完成：

- 功能代码已实际实现，不是 TODO、占位代码或空壳页面
- 前端与后端真实连通
- 正式功能不得使用 Mock 数据冒充真实数据
- 数据能够正确写入并重新读取数据库
- 页面刷新后数据仍然正确
- 正常流程能够完成
- 主要异常流程有明确处理
- 权限校验有效
- 必要日志完整
- Unit Test 通过
- API Test 通过
- 相关 Integration Test 通过
- 修改不得破坏已有测试
- 前端无明显 Console Error
- 后端无未处理 Exception
- 不允许硬编码 Secret、Token、Password
- 数据库 Migration 可正常执行
- 相关文档已同步更新
- 验收证据已记录
- 完成 Git Commit

以下情况不得视为“完成”：

- 只有页面，没有真实后端
- 只有 API，没有前端调用
- 只有数据库表，没有业务流程
- 使用静态 JSON / Mock 数据代替正式实现
- 测试代码跳过关键逻辑
- 为了让测试通过而删除断言
- 捕获异常后静默忽略
- Connector 只有接口定义，没有真实验证，却声明平台已接入
- AI 返回看似合理的内容，但没有调用真实业务数据
- 代码可以编译，但核心业务流程没有实际运行

---

# 35. Phase 级验收 Gate

每个 Phase 必须经过：

```text
Implementation
     ↓
Unit Test
     ↓
Integration Test
     ↓
Acceptance Test
     ↓
Regression Test
     ↓
Acceptance Report
     ↓
Git Commit
```

当前 Phase 未通过验收时，不得因为“代码基本完成”而直接宣布完成。

可以继续开发其他不依赖模块，但必须在报告中明确标记：

```text
PASS
FAIL
BLOCKED
NOT_IMPLEMENTED
```

不得把 `BLOCKED` 或 `NOT_IMPLEMENTED` 写成 `PASS`。

---

# 36. Phase 1 — 基础设施验收

必须验证：

- Frontend 能正常启动
- Backend 能正常启动
- PostgreSQL 能连接
- Redis 能连接
- Worker 能启动并执行测试任务
- Docker Compose 可以启动完整开发环境
- 环境变量配置有效
- 数据库 Migration 可以从空数据库执行
- 停止并重新启动后数据仍存在
- Health Check 正常

最低验收流程：

```text
docker compose up
↓
Frontend Ready
↓
Backend Ready
↓
PostgreSQL Ready
↓
Redis Ready
↓
Worker Ready
↓
执行 Migration
↓
调用 Health API
↓
PASS
```

---

# 37. IAM 验收

必须验证：

- 注册
- 登录
- Token 获取
- Token 失效
- 未登录访问受保护 API
- 用户信息查询
- Role 创建
- Permission 创建
- Role 与 Permission 关联
- 用户与 Role 关联
- RBAC 权限生效

关键验收：

```text
普通用户
↓
访问管理员 API
↓
403

管理员
↓
访问管理员 API
↓
成功
```

不得只在前端隐藏按钮代替后端权限控制。

---

# 38. Commerce 验收

## 38.1 Product

必须支持：

1. 创建商品
2. 查询商品
3. 编辑商品
4. 删除或归档商品
5. 搜索商品
6. 分页
7. SKU / Variant 管理
8. 商品与库存关联

验收流程：

```text
前端创建商品
↓
Backend API
↓
PostgreSQL
↓
重新查询
↓
前端列表显示
↓
编辑
↓
刷新页面
↓
修改仍然存在
↓
归档/删除
↓
状态正确
```

不得使用前端本地 Mock 数据。

## 38.2 Order

必须验证：

- 创建/导入订单
- Order Item 正确
- 金额正确
- 币种正确
- 状态变化正确
- 分页与搜索正确
- 店铺隔离正确
- 同一个外部订单不能重复创建

## 38.3 Inventory

必须验证：

- 库存增加
- 库存减少
- Inventory Log
- 并发更新
- 库存不得出现不允许的负数
- 重复事件不得重复扣库存
- 库存变化可追溯

---

# 39. Store 验收

必须验证：

- 创建店铺
- 修改店铺
- 禁用店铺
- 平台类型正确
- 店铺与用户/组织关系正确
- Credential 安全存储
- 不同店铺数据隔离
- 一个用户无权访问其他无授权店铺

敏感信息：

- 不得出现在日志
- 不得返回给无权限前端
- 不得提交 Git

---

# 40. Connector 验收

至少选择一个平台完成真实集成后，才允许声明“真实平台接入完成”。

真实 Connector 必须完成：

```text
平台授权
↓
获取真实店铺
↓
获取商品
↓
Connector 转换
↓
UnifiedProduct
↓
写入 PostgreSQL
↓
前端显示
```

订单：

```text
平台订单
↓
Connector
↓
UnifiedOrder
↓
PostgreSQL
↓
前端订单页面
```

必须测试：

- Token 失效
- API 超时
- Rate Limit
- 网络错误
- 分页
- 空数据
- 部分字段缺失
- 平台返回异常
- 重复同步
- 同步中断后重新执行

关键要求：

> 重复同步同一个外部商品或订单，不得产生重复核心数据。

平台原始 DTO 不得泄漏到 Commerce Domain。

尚未取得真实平台凭据时，可以使用 Sandbox / Fake Connector 做开发测试，但验收报告必须明确写为：

```text
REAL_INTEGRATION: NOT_VERIFIED
```

不得把模拟集成描述为真实平台验收通过。

---

# 41. Finance 验收

Finance 属于高风险模块，验收标准高于普通 CRUD。

必须覆盖：

- Payment
- PaymentTransaction
- Refund
- RefundTransaction
- Settlement
- SettlementItem
- Reconciliation
- FinanceLedger

必须测试：

- 正常支付
- 支付失败
- 重复支付请求
- 重复 Webhook
- 非法 Webhook 签名
- 全额退款
- 部分退款
- 重复退款
- 超额退款
- 结算
- 手续费
- 多币种
- 汇率
- 对账差异

必须保证：

```text
同一个 Idempotency Key
↓
重复请求 N 次
↓
只能产生一次有效交易
```

金额处理：

- 禁止使用 float
- 使用 Decimal 或最小货币单位整数
- 明确 currency
- 明确 rounding 规则

退款必须满足：

```text
累计退款金额 <= 可退款金额
```

财务数据必须：

- 可追溯
- 有 Transaction ID
- 有时间
- 有来源
- 有状态变化记录
- 关键操作有 Audit Log

如果使用 Sandbox 支付环境，报告必须明确标记 Sandbox，不得描述为生产支付验证。

---

# 42. Analytics 验收

至少验证：

- GMV
- 销售额
- 订单量
- 客单价
- 退款率
- 实际到账
- 平台手续费
- 支付手续费
- 利润

验收方式不能只看 Dashboard。

必须使用一组已知输入数据人工计算期望结果，再与系统输出比较。

例如：

```text
订单收入 = 1000
退款 = 100
平台费 = 50
支付费 = 20
其他已计入成本 = 200

系统结果必须与当前定义的利润公式一致。
```

所有指标必须在文档中定义计算公式，避免前后端、AI 和报表使用不同口径。

---

# 43. LLM Gateway 验收

必须验证：

- Provider 可以正常切换
- API Key 不硬编码
- Timeout
- Retry
- Provider Error
- Rate Limit
- Token Usage 记录
- 请求日志不泄漏 Secret
- 流式输出可以正常结束
- 模型返回异常格式时系统不会崩溃

业务模块不得绕过 LLM Gateway 直接调用模型 Provider。

---

# 44. Agent 验收

Agent 不能以“回答看起来正确”作为验收标准。

测试示例：

```text
用户：
“查询最近 30 天销售情况”
```

必须：

```text
Agent
↓
正确选择 Analytics Tool
↓
Tool 查询真实业务数据
↓
返回 Tool Result
↓
LLM 基于 Tool Result 回答
```

必须验证：

- Tool Selection
- Tool Arguments
- Tool Result
- Agent Final Answer
- Tool Failure
- Permission
- Timeout
- 无数据场景

禁止：

> LLM 在没有业务数据的情况下自行编造销售额、订单量、利润、退款率等数据。

Tool 调用失败时，必须明确处理失败状态，不得使用模型猜测数据补齐。

Agent 的 Tool 调用必须受到与普通 API 相同的权限约束。

---

# 45. RAG 验收

必须准备固定测试集，至少包含：

- 明确命中
- 同义表达
- 多文档
- 无相关文档
- 错误问题
- 上下文追问

验证：

```text
Question
↓
Retrieval
↓
Top-K
↓
Rerank
↓
Context
↓
Answer
```

必须记录：

- 检索到哪些 Chunk
- Retrieval Score
- 最终使用哪些 Context
- 是否有来源
- 无证据时是否拒绝编造

RAG 无相关资料时，不得把模型自身知识伪装成知识库检索结果。

---

# 46. Worker 验收

必须验证：

- Task 创建
- Worker 消费
- Task 成功
- Task 失败
- Retry
- Timeout
- Worker 重启
- 重复任务
- Task 状态查询

关键任务必须保证适当的幂等性。

例如：

```text
Order Sync Task
执行
↓
Worker 中途崩溃
↓
重新启动
↓
再次执行
↓
不得制造重复订单
```

---

# 47. 前端验收

每个正式页面至少验证：

- Loading
- Empty
- Success
- Error
- Permission Denied

表单验证：

- Required
- Invalid Input
- Server Error
- Duplicate Submit

必须检查：

- 无明显 Console Error
- API Error 有用户可理解的提示
- 页面刷新状态正确
- 列表分页正确
- 搜索/筛选正确
- 删除等危险操作需要确认
- 按钮不能是假功能

禁止存在点击按钮后：

```text
无请求
无提示
无结果
```

却被标记为完成的功能。

---

# 48. API 验收

核心 API 必须验证：

```text
2xx
400
401
403
404
409
422
5xx
```

根据实际接口语义选择适用状态。

同时验证：

- 参数校验
- Authentication
- Authorization
- Pagination
- Error Response
- Idempotency
- Rate Limit（需要的接口）
- Trace / Request ID（如已实现）

OpenAPI 文档必须可以正常生成。

---

# 49. 数据库验收

必须验证：

- 全新数据库 Migration 成功
- 升级 Migration 成功
- Foreign Key 正确
- Unique Constraint 正确
- Index 基本合理
- Transaction 正确
- Rollback 正确
- Decimal 精度正确
- 时间字段规则统一
- 删除策略明确

不得依赖开发者本机手工修改数据库才能运行。

---

# 50. Security 验收

至少检查：

- Secret 不进入 Git
- Password 正确 Hash
- JWT 验证
- RBAC
- CORS
- SQL Injection 基础防护
- XSS 基础防护
- Credential 不写日志
- Webhook 验签
- 敏感 API 权限
- 文件上传限制
- 错误信息不泄漏内部 Secret

必须运行 Secret Scan 或等价检查。

---

# 51. Regression 验收

每完成一个 Phase：

```text
新功能测试
+
此前全部关键测试
```

必须再次执行。

禁止：

```text
Phase 8 PASS
但是 Phase 3 已经坏了
```

这种状态仍然声明项目正常。

---

# 52. 最终端到端验收（E2E）

V1 最终必须至少跑通一次完整业务闭环：

```text
用户注册 / 登录
↓
创建或连接店铺
↓
平台授权
↓
同步商品
↓
同步订单
↓
库存更新
↓
Payment / Refund / Settlement 数据
↓
Finance
↓
Analytics Dashboard
↓
Agent 查询真实业务数据
↓
RAG 查询知识库
↓
最终结果返回前端
```

任何关键环节无法运行时，必须在最终报告中明确说明。

---

# 53. 验收报告

项目必须生成：

```text
ACCEPTANCE_REPORT.md
```

至少包含：

```text
1. Build 信息
2. Git Commit SHA
3. 运行环境
4. 功能验收
5. 前端验收
6. API 验收
7. 数据库验收
8. Connector 验收
9. Finance 验收
10. AI / Agent 验收
11. RAG 验收
12. Worker 验收
13. Security 检查
14. Regression Test
15. E2E 验收
16. 测试数量与结果
17. 已知问题
18. 未完成功能
19. Blocked 项
20. 最终状态
```

状态只允许：

```text
PASS
PASS_WITH_KNOWN_ISSUES
FAIL
BLOCKED
```

禁止把未验证项目自动视为 PASS。

---

# 54. 验收证据

关键验收项应保留可复查证据，例如：

- Test Output
- API Response
- Database Query Result
- Connector Sync Result
- Worker Task Result
- E2E Test Result
- 必要的截图
- 日志片段

验收报告应指向这些证据，而不是只写：

```text
测试通过
```

---

# 55. AI 开发完成判定规则

AI 编程工具不得因为以下理由自行宣布任务完成：

- “代码已经写完”
- “理论上可以运行”
- “接口已经创建”
- “页面已经创建”
- “测试文件已经生成”
- “Mock 测试通过”

正确完成流程必须是：

```text
Implement
↓
Run
↓
Test
↓
Verify
↓
Acceptance
↓
Regression
↓
Document
↓
Git Commit
```

如果因为缺少真实账号、API Key、支付 Sandbox、平台审核等外部条件无法完成验证：

必须标记：

```text
BLOCKED
```

并说明：

```text
Blocked Reason
Required External Resource
Already Verified Parts
Unverified Parts
How To Continue Verification
```

不得猜测真实环境能够正常工作。

---

# 56. Git 验收要求

每个 Phase 通过对应验收后必须提交 Git。

Commit 应保持单一职责，例如：

```text
feat(iam): add RBAC authentication
feat(commerce): add product management
feat(connectors): add Shopify connector
feat(finance): add payment transaction model
feat(ai): add LLM gateway
feat(agent): add capability registry
test(finance): add refund idempotency tests
```

提交前至少执行：

```text
format / lint
↓
unit tests
↓
integration tests
↓
relevant acceptance tests
```

主分支必须保持可运行。

项目最终交付必须有一个明确的 Git Commit SHA 与 `ACCEPTANCE_REPORT.md` 对应。
