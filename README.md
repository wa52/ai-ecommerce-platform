# AI 跨境电商平台（Phase 1 骨架）

**AI-Native Multi-Platform E-Commerce Platform**：Saleor 作为 Commerce Core，FastAPI 作为 AI 扩展层（架构定义见 `PROJECT_SPEC.md` §2.1）。

## 外部依赖

| 依赖 | 要求 | 用途 |
| --- | --- | --- |
| Docker Desktop | ≥ 5 GB 内存配额 | 运行全部组件 |
| Node.js | ≥ 22（前端本地开发） | Next.js |
| Python | ≥ 3.13（后端本地开发） | FastAPI |

`Dockerfile` 内部使用 `ghcr.io/saleor/saleor:3.23`、`postgres:16 (pgvector)`、`redis:7`、`minio`，无需本机安装这些软件。

## 环境变量

复制 `.env.example` 为 `.env` 并修改：

```text
POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB   # PostgreSQL 业务库（必填）
SALEOR_DB                                          # Saleor 库名
SALEOR_SECRET_KEY                                  # Saleor 密钥（必填）
MINIO_ROOT_USER / MINIO_ROOT_PASSWORD              # MinIO
AI_DB                                              # AI 扩展层数据库名
```

> 不要把真实密钥提交到 Git。

## 本地启动与验证

```bash
# 1. 启动全部组件
docker compose up -d

# 2. 初始化 Saleor 数据库（从空库执行 migration）
docker compose exec saleor-api python3 manage.py migrate

# 3. 创建 Saleor 管理员
docker compose exec saleor-api python3 manage.py createsuperuser --email admin@example.com
#    随后设置密码（也可用交互式创建）
docker compose exec saleor-api python3 manage.py shell -c "from saleor.account.models import User; u=User.objects.get(email='admin@example.com'); u.set_password('<your-password>'); u.save()"

# 4. 执行 AI 扩展层 Migration
docker compose exec ai-backend alembic upgrade head
```

> `saleor` 与 `ai_platform` 数据库由 `db/init/create-databases.sh` 在数据库卷首次初始化时自动创建。
> 若数据库卷已存在（早于该脚本），需手动创建一次：
> `docker compose exec db psql -U <POSTGRES_USER> -d postgres -c "CREATE DATABASE saleor"`（`ai_platform` 同理）。

运行后访问：

| 服务 | 地址 |
| --- | --- |
| 平台前端（本阶段：系统状态面板） | http://localhost:3000 |
| AI 扩展层 Health API | http://localhost:8001/api/v1/health |
| Saleor GraphQL | http://localhost:8000/graphql/ |
| Saleor 商家后台 | http://localhost:9000 |
| MinIO 控制台 | http://localhost:9001 |
| Mailpit（邮件测试） | http://localhost:8025 |
| Jaeger UI | http://localhost:16686 |

前端环境变量（本地开发用）：`NEXT_PUBLIC_AI_API_URL`（默认 `http://localhost:8001/api/v1`）。

## 本地开发（容器外）

```bash
# 后端
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\pytest          # 单元测试
.venv\Scripts\uvicorn app.main:app --reload --port 8001

# 前端
cd frontend
npm install
npm run dev            # http://localhost:3000
npm run build          # 生产构建
```

## 架构（Phase 1）

```text
Next.js Storefront/Admin (3000)
        │
FastAPI AI 扩展层 (8001) ── Commerce Adapter ──> Saleor GraphQL (8000)
        │                                            │
PostgreSQL(pgvector) + Redis + MinIO         Celery Worker + Dashboard(9000)
```

- Commerce 核心能力（商品/订单/库存/支付）由 Saleor 提供，AI 层禁止直接读写 Saleor 数据库。
- AI 层通过 `app/connectors/`（Commerce Adapter）访问 Saleor GraphQL API。

## API（AI 扩展层）

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/health` | GET | PostgreSQL / Redis / Saleor 连通检查 |
| `/api/v1/tasks` | POST | 提交 Worker 任务（202） |
| `/api/v1/tasks/{id}` | GET | 查询任务状态与结果 |
| `/api/v1/iam/login` | POST | 登录（代理 Saleor `tokenCreate`），返回 token |
| `/api/v1/iam/me` | GET | 当前用户（需 `Authorization: Bearer <token>`） |
| `/api/v1/iam/admin/overview` | GET | 管理员概览（需 staff，否则 403） |

身份来源为 Saleor：AI 层不保存密码、不复制用户表，只做令牌校验与授权（RBAC）。

## 验收

- 验收报告：`ACCEPTANCE_REPORT.md`
- 可复查证据：`docs/evidence/phase1/`、`docs/evidence/phase2/`
- 后端测试：`cd backend; .venv\Scripts\python -m pytest`
- 验收脚本（需环境变量提供凭据）：
  - `backend/scripts/iam_acceptance.py`（`IAM_ADMIN_EMAIL` / `IAM_ADMIN_PASSWORD` / `IAM_CUSTOMER_EMAIL` / `IAM_CUSTOMER_PASSWORD`）
  - `backend/scripts/saleor_acceptance.py`（`SALEOR_ADMIN_EMAIL` / `SALEOR_ADMIN_PASSWORD`）
  - `backend/scripts/acceptance_worker_check.py`

## 发布到 GitHub

项目位于 `D:\AiProjects` umbrella 仓库内。用脚本抽取本项目独立历史并推送（不影响其他项目）：

```powershell
powershell -File scripts\push_github.ps1 -Message "feat(xxx): ..."
```

## 环境变量（完整清单）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 是 | PostgreSQL 业务库 |
| `SALEOR_DB` / `SALEOR_SECRET_KEY` | 是 | Saleor 库与密钥 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | 是 | 对象存储 |
| `STORE_CREDENTIAL_KEY` | 是 | 店铺凭据加密（Fernet，32 字节 urlsafe base64） |
| `PAYMENT_WEBHOOK_SECRET` | 是 | 支付 Webhook HMAC 验签密钥 |
| `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 否 | LLM Gateway（留空则未配置，AI 接口返回 503） |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | 否 | 嵌入（默认 `hashing`，生产建议 `openai_compatible`） |
| `SHOPIFY_SHOP_DOMAIN` / `SHOPIFY_ACCESS_TOKEN` / `SHOPIFY_API_SCHEME` | 否 | Shopify Connector（留空则 `REAL_INTEGRATION: NOT_VERIFIED`） |
| `LOG_LEVEL` | 否 | 日志级别（默认 dev=DEBUG，其他=INFO） |
| `CORS_ORIGINS` | 否 | 允许的前端来源（JSON 数组） |

生成 Fernet 密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 生产部署注意事项

- 所有必填密钥必须由环境注入，禁止写入镜像或提交到 Git。
- `ai-backend` 启动时执行依赖自检（PostgreSQL / Redis / Saleor），失败即拒绝启动并输出可操作错误。
- 启动后执行 `alembic upgrade head`；`saleor-api` 执行 `python3 manage.py migrate`。
- 服务已内置：请求 ID（`X-Request-ID`）、安全响应头、统一异常出口（不泄漏内部细节）、登录限流（Redis）。
- 生产建议：为 `document_chunks.embedding` 建立 pgvector ANN 索引、配置真实 LLM/Embedding 服务、将批量同步与嵌入任务放入 Worker。

## 验收与证据

- 验收报告：`ACCEPTANCE_REPORT.md`（Phase 1–10，含每 Phase 的 PASS/BLOCKED 与证据索引）
- 证据目录：`docs/evidence/phase1` … `docs/evidence/phase10`
- 测试：`cd backend; .venv\Scripts\python -m pytest --cov=app`（121 passed，覆盖率 80%）
- 验收脚本（凭据均由环境变量提供）：
  | 脚本 | 用途 |
  | --- | --- |
  | `iam_acceptance.py` | 登录 / 401 / 403 / RBAC |
  | `commerce_acceptance.py` | 商品 / SKU / 库存 / 订单（真实 Saleor） |
  | `connector_acceptance.py` | Connector + Store 凭据加密（Sandbox Shopify） |
  | `finance_acceptance.py` | 支付 / 退款 / 结算 / 对账 / Webhook |
  | `ai_acceptance.py` | LLM Gateway / 文案 / 翻译 / 流式 / Usage |
  | `agent_acceptance.py` | Agent 工具选择 / 失败 / 权限 / 真实数据 |
  | `rag_acceptance.py` | 知识库 / 检索 / 拒答 / 引用 |
  | `analytics_acceptance.py` | 指标口径 + 人工核算 + SQL 交叉核对 |
  | `concurrency_acceptance.py` | 并发库存 / 并发重复支付幂等 |
  | `e2e_acceptance.py` | 最终端到端业务闭环（§52） |
  | `secret_scan.py` | Secret 扫描（§50） |
