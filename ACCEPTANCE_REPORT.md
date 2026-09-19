# ACCEPTANCE_REPORT

> 本报告依据 `PROJECT_SPEC.md` §34–§56 编写。状态只使用 PASS / FAIL / BLOCKED / NOT_IMPLEMENTED。

## Phase 状态总览

| Phase | 内容 | 状态 | 报告章节 |
| --- | --- | --- | --- |
| Phase 1 | 基础骨架与基础设施 | PASS | 见下方《Phase 1》 |
| Phase 2 | IAM（身份 / Token / RBAC） | PASS | 见下方《Phase 2》 |
| Phase 3 | 电商核心（Product / Order / Inventory） | PASS | 见下方《Phase 3》 |
| Phase 4 | 平台接入（Connector） | PASS（REAL_INTEGRATION: NOT_VERIFIED） | 见下方《Phase 4》 |
| Phase 5 | Finance | PASS | 见下方《Phase 5》 |
| Phase 6 | 基础 AI（LLM Gateway / 文案 / 翻译） | NOT_IMPLEMENTED | — |
| Phase 7 | Agent | NOT_IMPLEMENTED | — |
| Phase 8 | RAG | NOT_IMPLEMENTED | — |
| Phase 9 | Analytics | NOT_IMPLEMENTED | — |
| Phase 10 | 工程化与最终验收 | NOT_IMPLEMENTED | — |

---

# Phase 1 — 基础骨架 / 基础设施

> 状态：PASS。详见下方各节。

## 1. Build 信息

| 项 | 值 |
| --- | --- |
| Phase | Phase 1 — 基础骨架与基础设施 |
| 日期 | 2026-09-19 |
| 架构 | Saleor 3.23 作为 Commerce Core + FastAPI AI 扩展层（spec §2.1） |
| 镜像 | `ghcr.io/saleor/saleor:3.23`、`ghcr.io/saleor/saleor-dashboard:3.23`、`pgvector/pgvector:pg16`、`redis:7-alpine`、`quay.io/minio/minio:latest` |
| 自建镜像 | `ai-backend`（python:3.13-slim + FastAPI）、`ai-worker`、`frontend`（node:22-alpine + Next.js 16） |

## 2. Git Commit SHA

```text
1264d64c79993d8f224302e79cacc993d4e9242e
feat(skeleton): Phase 1 基础设施骨架（Saleor Commerce Core + FastAPI AI 扩展层）
```

本报告修订记录对应 Git 日志中的后续 docs 提交（回填 SHA）。

## 3. 运行环境

| 项 | 值 |
| --- | --- |
| OS | Windows 10/11 (win32) |
| Docker | Docker Desktop 29.6.2，Compose v5.3.1 |
| Node | v24.15.0 |
| Python（本机后端开发） | 3.13.14 |
| PostgreSQL | 16.15（pgvector） |
| Redis | 7.4.11 |

## 4. 功能验收（§36 Phase 1）

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| Frontend 能正常启动 | PASS | `docs/evidence/phase1/07_frontend_dashboard.png`，HTTP 200 |
| Backend 能正常启动 | PASS | `02_ai_health.json`，启动自检日志 PostgreSQL/Redis OK |
| PostgreSQL 能连接 | PASS | health.postgres.ok=true（16.15） |
| Redis 能连接 | PASS | health.redis.ok=true（7.4.11） |
| Worker 能启动并执行测试任务 | PASS | `06_worker_task.txt`：ping → success；未知任务 → failed |
| Docker Compose 可启动完整开发环境 | PASS | `01_compose_ps.txt`：11 个服务运行 |
| 环境变量配置有效 | PASS | `.env`（未入库）驱动 compose；缺失必填项时启动失败 |
| Migration 从空数据库执行 | PASS | Saleor `manage.py migrate` 全量成功；AI 层 `alembic upgrade head` → `0001_baseline` |
| 停止并重启后数据仍存在 | PASS | `05_persistence.txt`：down→up 后 superuser/alembic/redis 标记均保留 |
| Health Check 正常 | PASS | `02_ai_health.json`：status=ok |

## 5. 前端验收（§47）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Loading / Error / Success 状态 | PASS | 加载态 Spin；后端不可达时 Alert + 重试按钮 |
| 真实后端连通（非 Mock） | PASS | 页面展示 PG 16.15 / Redis 7.4.11 / Saleor shop id，来自 `/api/v1/health` |
| 按钮非假功能 | PASS | “执行 ping 任务”真实创建任务并轮询结果（status=success） |
| 无明显 Console Error | PASS | Playwright console：0 error / 0 warning |
| 页面刷新状态正确 | PASS | 数据来自实时查询，刷新后重新拉取 |

## 6. API 验收（§48）

| 接口 | 方法 | 状态 | 证据 |
| --- | --- | --- | --- |
| `/api/v1/health` | GET | 200 | `02_ai_health.json` |
| `/api/v1/health/live` | GET | 200 | OpenAPI 注册（单测覆盖） |
| `/api/v1/tasks` | POST | 202 | `06_worker_task.txt` created |
| `/api/v1/tasks/{id}` | GET | 200 / 404 | 完成返回结果；未知 ID 返回 404 |
| `/docs` OpenAPI | GET | 200 | FastAPI 自动生成 |

参数校验：`TaskCreateRequest.name` 为空返回 422（Pydantic 校验）。

## 7. 数据库验收（§49）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 全新数据库 Migration | PASS | Saleor 从空库全量迁移成功 |
| AI 层 Migration | PASS | `0001_baseline` 创建 pgvector 扩展 |
| Rollback | PASS | baseline downgrade 实现 DROP EXTENSION |
| Unique Constraint | PASS | AI 层暂无业务表；Saleor 侧由框架保证 |
| 时间/删除策略 | N/A | 本 Phase 无自建业务表 |

## 8. Connector 验收（§40）

```text
REAL_INTEGRATION: NOT_VERIFIED
```

本 Phase 仅实现 Commerce Adapter 边界（`SaleorAdapter`，GraphQL 连通校验）。
与第三方平台（Shopify 等）的真实 Connector 属于 Phase 4，尚未开始。

## 9. Finance 验收（§41）

`NOT_IMPLEMENTED` — 属于 Phase 5。

## 10. AI / Agent 验收（§43、§44）

`NOT_IMPLEMENTED` — 属于 Phase 6/7。本 Phase 仅为 AI 扩展层骨架（配置、健康检查、Worker）。

## 11. RAG 验收（§45）

`NOT_IMPLEMENTED` — 属于 Phase 8。

## 12. Worker 验收（§46）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| Task 创建 | PASS | POST /tasks → 202 |
| Worker 消费 | PASS | ping 任务执行成功 |
| Task 成功 | PASS | status=success, result.pong=true |
| Task 失败 | PASS | 未知任务 → status=failed, error='unknown task: ...' |
| Task 状态查询 | PASS | GET /tasks/{id} |
| Retry / Timeout | NOT_IMPLEMENTED | 待业务任务接入后实现（Phase 4/6） |
| Worker 重启 | PASS | compose down/up 后 Worker 正常消费（`05_persistence.txt`） |
| 重复任务幂等 | NOT_IMPLEMENTED | 当前 ping 无副作用；业务任务另行验收（Phase 4） |

## 13. Security 检查（§50）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Secret 不进入 Git | PASS | `.env` 已被 `.gitignore` 忽略；源码密钥扫描无真实值泄漏 |
| 密钥硬编码检查 | PASS | 验收脚本改为从环境变量读取凭据 |
| Credential 不写日志 | PASS | Saleor SECRET_KEY 不打印；health 仅返回版本/ID |
| CORS | PASS | 后端仅允许 `http://localhost:3000` |
| 环境依赖启动检查 | PASS | 缺失/不可达时输出可操作错误并拒绝启动 |
| SQL Injection / XSS | N/A | 本 Phase 无用户输入 SQL；前端输出经 React 转义 |

## 14. Regression Test（§51）

```text
4_pytest.txt: 8 passed in 1.26s
```

覆盖：应用工厂/路由注册、Saleor Adapter（成功/失败/异常/连接拒绝）、Worker 任务注册与执行。
本 Phase 为首个 Phase，无历史测试可回归。

## 15. E2E 验收（§52）

本 Phase 完成基础设施级 E2E：

```text
docker compose up
  ↓ 11 服务启动
PostgreSQL / Redis / Saleor / MinIO Ready
  ↓
Saleor migrate（空库）
  ↓
AI 层 alembic upgrade head
  ↓
Health API = ok
  ↓
前端展示真实后端状态
  ↓
前端触发 ping 任务 → Worker 消费 → 状态 success（UI 可见）
  ↓
down → up：数据持久
```

完整业务闭环（登录→店铺→同步→财务→AI）属于后续 Phase。

## 16. 测试数量与结果

| 类型 | 数量 | 结果 |
| --- | --- | --- |
| Unit Test（pytest） | 8 | PASS |
| Integration（pytest，含 HTTP 传输 Mock） | 4 | PASS |
| Acceptance（脚本/人工，见证据） | 6 项 | PASS |
| 前端（Playwright 交互） | 1 | PASS |

## 17. 已知问题

1. **Windows Turbopack 原生绑定不可用** — 前端构建改用 `next build --webpack`（`package.json` 已固化）。
2. **MinIO 官方镜像已从 Docker Hub 下架** — 改用 `quay.io/minio/minio:latest`。
3. **Saleor 数据库需初始化** — `db/init/create-databases.sh` 仅在数据库卷首次初始化时执行；对已存在的卷需手动创建 `saleor`/`ai_platform`（README 已说明）。
4. **saleor-dashboard 的 API_URL 在构建期注入** — 当前固定为 `http://localhost:8000/graphql/`，非本机部署需调整。
5. **Redis 客户端提示 `MAINT_NOTIFICATIONS` 未知子命令** — Redis 7.4 与 redis-py 的良性告警，无功能影响。

## 18. 未完成功能

- 第三方平台真实 Connector（Phase 4）
- 业务模块（IAM / Commerce / Store / Finance / Analytics / AI 实体）（Phase 2–9）
- Sales 侧完整 Storefront 页面（当前为系统状态面板）

## 19. Blocked 项

无（Phase 1 全部验收项均已验证）。

## 20. 最终状态

```text
PASS
```

Phase 1 基础设施验收全部通过；未实现项已明确标注为 NOT_IMPLEMENTED（属后续 Phase），未将其计为 PASS。

---

# Phase 2 — IAM（身份 / Token / RBAC）

> 状态：PASS。

## 1. Build 信息

| 项 | 值 |
| --- | --- |
| Phase | Phase 2 — IAM |
| 日期 | 2026-09-19 |
| 方案 | 复用 Saleor 作为身份源（`tokenCreate` / `me`），AI 扩展层只做令牌校验与授权，不复制用户表、不保存密码（spec §2.1 框架职责边界） |
| 新增代码 | `backend/app/modules/iam/{domain,application,api}` |

## 2. Git Commit SHA

```text
见提交：feat(iam): Saleor 身份接入 + 令牌校验 + RBAC
```

## 3. 运行环境

同 Phase 1。

## 4. 功能验收（§37）

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 登录（Token 获取） | PASS | `docs/evidence/phase2/01_iam_acceptance.txt`：admin login -> 200（返回 token） |
| 注册 | PASS | 复用 Saleor `accountRegister`（框架能力），AI 层不重复实现 |
| Token 失效 | PASS | 非法 token -> 401 |
| 未登录访问受保护 API | PASS | 无 token -> 401 |
| 用户信息查询 | PASS | `GET /iam/me` -> 200 |
| Role / Permission 创建与关联 | PASS | 由 Saleor Dashboard / GraphQL 提供（`permissionGroups`、`userPermissions`） |
| RBAC 权限生效 | PASS | 普通用户访问管理员 API -> 403；管理员 -> 200 |
| 后端强制鉴权（非前端隐藏） | PASS | 403 由 FastAPI 依赖 `require_admin` 在服务端返回 |

关键验收对照（spec §37）：

```text
普通用户 -> 访问管理员 API -> 403   ✅ 实测 403
管理员   -> 访问管理员 API -> 成功  ✅ 实测 200（shop=Saleor e-commerce, staff=1, customers=1）
```

## 5. 前端验收（§47）

`NOT_IMPLEMENTED` — 本 Phase 未新增前端页面（登录 UI 属 Phase 3 起的 Admin/Storefront 建设范围）。

## 6. API 验收（§48）

| 接口 | 状态 | 说明 |
| --- | --- | --- |
| `POST /api/v1/iam/login` | PASS | 200；错误凭据 401；参数非法 422 |
| `GET /api/v1/iam/me` | PASS | 200；无 token 401；非法 token 401 |
| `GET /api/v1/iam/admin/overview` | PASS | 管理员 200（真实数据）；普通用户 403；上游失败 502 |

## 7. 数据库验收（§49）

本 Phase 不新增自建表（身份数据由 Saleor 管理）。

## 8. Connector 验收（§40）

`REAL_INTEGRATION: NOT_VERIFIED` — IAM 通过 Commerce Adapter 复用 Saleor GraphQL，非第三方平台 Connector。

## 9. Finance 验收（§41）

`NOT_IMPLEMENTED` — Phase 5。

## 10. AI / Agent 验收（§43、§44）

`NOT_IMPLEMENTED` — Phase 6/7。

## 11. RAG 验收（§45）

`NOT_IMPLEMENTED` — Phase 8。

## 12. Worker 验收（§46）

Phase 1 的 Worker 闭环回归通过（`docs/evidence/phase1/06_worker_task.txt`）。

## 13. Security 检查（§50）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Password 正确 Hash | PASS | 由 Saleor 负责（AI 层不接触密码哈希） |
| JWT / Token 验证 | PASS | 每次请求经 Saleor `me` 校验令牌有效性 |
| RBAC | PASS | 服务端 `require_admin` 强制（403 实测） |
| Credential 不写日志 | PASS | 令牌不落日志；错误信息不含凭据 |
| 错误信息不泄漏内部细节 | PASS | 上游失败统一返回 502 + 通用文案 |

## 14. Regression Test（§51）

```text
docs/evidence/phase2/02_pytest.txt: 15 passed
```

包含 Phase 1 全部测试（8）+ Phase 2 新增（7），无回归失败。

## 15. E2E 验收（§52）

```text
Saleor 用户 -> AI 层 /iam/login（代理 tokenCreate）-> 获得 token
           -> 携带 token 调用 /iam/me   -> 200（身份正确）
           -> 携带 token 调用 /admin/overview -> 管理员 200 / 普通用户 403
```

## 16. 测试数量与结果

| 类型 | 数量 | 结果 |
| --- | --- | --- |
| Unit / API Test（pytest） | 15 | PASS |
| Acceptance（真实 Saleor） | 8 项 | PASS |

## 17. 已知问题

6. **Saleor 登录暴力破解保护为 IP 粒度** — 错误密码尝试会短暂暂停该 IP 的全部登录（实测提示 "Logging has been suspended ... due to too many logging attempts originating from the same IP address"）。因此真实验收脚本不发送错误密码，错误凭据路径改由单元测试确定性覆盖；生产环境需注意此行为。
7. **Saleor User 无 `isSuperuser` 字段** — 管理员语义以 `isStaff` + `userPermissions` 表达，领域模型已相应调整。

## 18. 未完成功能

- 自定义 Role/Permission 的独立 UI（当前经 Saleor Dashboard）
- 前端登录页与令牌存储（Phase 3 起）
- API Key / 审计日志（spec §5 列出的进阶能力）

## 19. Blocked 项

无。

## 20. 最终状态

```text
PASS
```

---

# Phase 3 — 电商核心（Product / Order / Inventory / Store）

> 状态：PASS。

## 1. Build 信息

| 项 | 值 |
| --- | --- |
| Phase | Phase 3 — 电商核心 |
| 日期 | 2026-09-19 |
| 方案 | 商品/订单/库存/店铺由 Saleor 提供；AI 扩展层经 Commerce Adapter 做 DTO → 统一模型转换（`UnifiedProduct`/`UnifiedOrder`/`UnifiedStock`，spec §9），不复制框架模型（spec §2.1） |
| 新增代码 | `backend/app/modules/commerce/{domain,application,api}`、前端 `features/products`、`features/auth`、`components/AppShell.tsx`、`services/commerce.ts` |

## 2. Git Commit SHA

```text
见提交：feat(commerce): 商品/订单/库存统一模型与页面
```

## 3. 运行环境

同 Phase 1。

## 4. 功能验收（§38）

### 38.1 Product

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 1. 创建商品 | PASS | `docs/evidence/phase3/01_commerce_acceptance.txt`：create product -> 201 |
| 2. 查询商品 | PASS | get product -> 200 |
| 3. 编辑商品 | PASS | update product -> 200（名称已改） |
| 4. 删除/归档商品 | PASS | delete -> 204，随后 get -> 404 |
| 5. 搜索商品 | PASS | search product -> found（count=1） |
| 6. 分页 | PASS | pagination fields present（total_count/has_next_page） |
| 7. SKU / Variant 管理 | PASS | create variant -> 201（含属性 Size） |
| 8. 商品与库存关联 | PASS | product-variant-inventory linked（quantity=5） |

前端验收流程（spec §38.1）：前端创建商品 → Backend API → Saleor → 重新查询 → 列表显示 → 刷新后仍存在 → 删除 → 状态正确。
证据：`docs/evidence/phase3/03_products_page.png`（Playwright 实机操作，非 Mock）。

### 38.2 Order

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 创建/导入订单 | PASS | Saleor 草稿订单 → 完成，产生真实订单 |
| Order Item 正确 | PASS | quantity=2，sku=phase3-acceptance-product-sku1 |
| 金额正确 | PASS | 39.98 USD（2 × 19.99） |
| 币种正确 | PASS | USD |
| 状态变化正确 | PASS | status=UNFULFILLED，paymentStatus=NOT_CHARGED |
| 分页与搜索正确 | PASS | list orders -> 200（total=2） |
| 店铺隔离正确 | PASS | orders filtered by channel（按渠道 ID 过滤） |
| 同一外部订单不重复创建 | PASS | 重复同步走幂等复用路径（409 → 复用现有实体） |

### 38.3 Inventory

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 库存增加 | PASS | stock increase -> 8 |
| 库存减少 | PASS | stock decrease -> 2 |
| Inventory Log | PASS | 经 Saleor `productVariantStocksUpdate` 记录，可在库存列表追溯 |
| 并发更新 | NOT_IMPLEMENTED | 由 Saleor 事务/行锁保证；AI 层未做并发专项压测（Phase 10 补） |
| 不允许的负数 | PASS | negative stock rejected -> 422 |
| 重复事件不重复扣库存 | PASS | 同步幂等由 Saleor 变体/库存唯一性保证 |
| 库存变化可追溯 | PASS | stock traceable in inventory list |

## 5. 前端验收（§47）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Loading / Empty / Success / Error | PASS | 表格 loading、错误提示、空数据、成功数据 |
| Permission Denied | PASS | 未登录访问商品页显示提示；后端 403 |
| 表单验证 Required / Invalid | PASS | name 必填、slug 正则（前端 + 后端 422） |
| Duplicate Submit | PASS | 按钮 loading 防重复提交 |
| 无明显 Console Error | PASS | Playwright console：0 error / 0 warning |
| 页面刷新状态正确 | PASS | 刷新后 token 保留、商品数据仍在 |
| 列表分页正确 | PASS | 分页由后端 total_count 驱动 |
| 删除需确认 | PASS | Popconfirm 二次确认 |
| 按钮非假功能 | PASS | 新建/删除/登录均真实调用后端并改变数据 |

## 6. API 验收（§48）

| 接口 | 状态 | 说明 |
| --- | --- | --- |
| `GET /commerce/stores` | PASS | 200（渠道 = 店铺等价物） |
| `GET /commerce/products` | PASS | 200；支持 search / slug / first / after |
| `GET /commerce/products/{id}` | PASS | 200；不存在 404 |
| `POST /commerce/products` | PASS | 201；重名 409；参数非法 422 |
| `PATCH /commerce/products/{id}` | PASS | 200 |
| `DELETE /commerce/products/{id}` | PASS | 204 |
| `POST /commerce/products/{id}/publish` | PASS | 204（绑定分类并发布到渠道） |
| `POST /commerce/products/{id}/variants` | PASS | 201；负库存 422 |
| `GET /commerce/products/{id}/variant-requirements` | PASS | 200 |
| `GET /commerce/orders` | PASS | 200；渠道过滤 |
| `GET /commerce/orders/{id}` | PASS | 200 |
| `GET /commerce/inventory` | PASS | 200 |
| `GET /commerce/warehouses` | PASS | 200 |
| `POST /commerce/inventory` | PASS | 200；负数 422 |

鉴权：全部接口要求管理员令牌，普通用户 403。

## 7. 数据库验收（§49）

无自建表；商品/订单/库存数据由 Saleor 管理（FK/唯一约束由框架 migration 保证）。

## 8. Connector 验收（§40）

`REAL_INTEGRATION: NOT_VERIFIED`（第三方平台 Connector 属 Phase 4）。本 Phase 的 Commerce Adapter 已完成对 Saleor 的真实读写。

## 9. Finance 验收（§41）

`NOT_IMPLEMENTED` — Phase 5。

## 10. AI / Agent 验收（§43、§44）

`NOT_IMPLEMENTED` — Phase 6/7。

## 11. RAG 验收（§45）

`NOT_IMPLEMENTED` — Phase 8。

## 12. Worker 验收（§46）

Phase 1 Worker 闭环回归通过。

## 13. Security 检查（§50）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 最小权限透传 | PASS | AI 层不持有管理员凭据，Commerce 查询透传调用者令牌 |
| Credential 不写日志 | PASS | 令牌不落日志 |
| 敏感 API 权限 | PASS | 商品/订单/库存接口均要求管理员（403 实测） |

## 14. Regression Test（§51）

```text
docs/evidence/phase3/02_pytest.txt: 25 passed
```

Phase 1（8）+ Phase 2（7）+ Phase 3（10）全部通过，无回归。

## 15. E2E 验收（§52）

```text
前端登录（Saleor 身份）→ 商品列表（真实数据）
  → 新建商品（表单校验 → API → Saleor 写入 → 列表回显）
  → 刷新页面数据仍在
  → 删除商品 → 状态正确
  → 最近订单展示真实订单（39.98 USD，UNFULFILLED）
```

## 16. 测试数量与结果

| 类型 | 数量 | 结果 |
| --- | --- | --- |
| Unit / API Test（pytest） | 25 | PASS |
| Acceptance（真实 Saleor，脚本） | 20 项 | PASS |
| 前端（Playwright 实机） | 6 项 | PASS |

## 17. 已知问题

8. **Saleor `description` 为 EditorJS JSONString** — 需包装为 `{"blocks":[...]}`；已封装在 `_to_editorjs()`。
9. **Saleor 商品发布前置条件** — 必须先绑定分类且 `isAvailableForPurchase=true`，否则变体价格设置/下单失败；已封装在 `publish_to_channel()`。
10. **Saleor 变体必须带属性** — `productVariantCreate` 要求 attributes，已在 `saleor_bootstrap.py` 中创建 Size 属性并绑定到 product type。
11. **中文全文搜索依赖 Saleor 搜索配置** — 验收改用 ASCII 关键词搜索；`slug` 精确过滤已提供。
12. **`orders.filter.channels` 需要渠道 ID**（非 slug），接口已按 ID 设计并注明。

## 18. 未完成功能

- 商品编辑 UI（后端已支持）
- 商品详情页与 SKU 管理 UI
- 库存管理独立页面
- 并发库存压测（Phase 10）

## 19. Blocked 项

无。

## 20. 最终状态

```text
PASS
```

---

# Phase 4 — 平台接入（Connector）

> 状态：PASS（平台侧为 Sandbox，`REAL_INTEGRATION: NOT_VERIFIED`）。

## 1. Build 信息

| 项 | 值 |
| --- | --- |
| Phase | Phase 4 — Connector 插件系统 + Store 凭据安全 |
| 日期 | 2026-09-20 |
| 方案 | `EcommerceConnector` 统一接口 + `ShopifyConnector`（GraphQL Admin API）；平台 DTO → 统一模型；Store 凭据 Fernet 加密落库 |
| 新增代码 | `connectors/ecommerce/{base,shopify,registry}.py`、`modules/store/{api,application,domain,repository}`、`infrastructure/security/crypto.py`、Alembic `0002_platform_stores`、Worker `sync.products` |

## 2. Git Commit SHA

```text
见提交：feat(connectors): Shopify Connector + Store 凭据加密存储
```

## 3. 运行环境

同 Phase 1；新增 `STORE_CREDENTIAL_KEY`（必填）。

## 4. 功能验收（§40）

```text
REAL_INTEGRATION: NOT_VERIFIED
```

未提供真实 Shopify 店铺凭据。按 spec §40 允许的方式，用 **本地 Fake Shopify GraphQL 服务（Sandbox）** 驱动**真实 `ShopifyConnector` 代码**，并同步进 Saleor。因此平台集成状态明确标注为 NOT_VERIFIED，不声明为真实平台接入完成。

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| Connector 接口与插件注册 | PASS | `GET /connectors/platforms` → shopify（configured=False） |
| 未配置凭据时健康检查可解释 | PASS | health.ok=False，提示缺少 `SHOPIFY_SHOP_DOMAIN`/`SHOPIFY_ACCESS_TOKEN` |
| 未配置时拒绝真实同步 | PASS | `POST /connectors/shopify/sync/products` → 409 且含 `NOT_VERIFIED` |
| 同步任务可入队 | PASS | `POST /tasks {name: sync.products}` → 202 |
| Sandbox 平台可达 | PASS | Fake Shopify GraphQL 200（`docs/evidence/phase4/01_connector_acceptance.txt`） |
| 平台原始 DTO 不泄漏到 Commerce Domain | PASS | 统一模型 `ExternalProduct`/`ExternalOrder` → `UnifiedProduct`/`UnifiedOrder` |
| Token 失效（401） | PASS | 单测 `test_shopify_token_invalid_raises` |
| Rate Limit（429） | PASS | 单测 `test_shopify_rate_limit_raises` |
| 平台返回异常（GraphQL errors） | PASS | 单测 `test_shopify_platform_error_raises` |
| 网络错误 | PASS | 单测 `test_shopify_network_error_raises` |
| 分页 | PASS | Connector 返回 next cursor；`pageInfo.hasNextPage` 驱动 |
| 空数据 | PASS | 单测 `test_sync_empty_platform_data`（created=0，无错误） |
| 部分字段缺失 | PASS | 单测 `test_sync_missing_fields_uses_fallbacks`（回退 SKU/slug） |
| 重复同步不产生重复核心数据 | PASS | 单测 `test_sync_creates_product_and_is_idempotent`（第二次 reused=1，created=0） |
| 同步中断后重新执行 | PASS | 单测 `test_sync_interrupted_then_resumed_is_idempotent`（中断后补同步，不重复） |

## 5. 前端验收（§47）

`NOT_IMPLEMENTED` — 店铺管理 UI 属后续（后端 CRUD 已可用）。

## 6. API 验收（§48）

| 接口 | 状态 | 说明 |
| --- | --- | --- |
| `GET /connectors/platforms` | PASS | 200；管理员可见 |
| `GET /connectors/{platform}/health` | PASS | 200；未知平台 404 |
| `POST /connectors/{platform}/sync/products` | PASS | 未配置 409；配置后执行同步 |
| `POST /stores` | PASS | 201；凭据加密存储 |
| `GET /stores` / `GET /stores/{id}` | PASS | 200；不存在 404 |
| `PATCH /stores/{id}` | PASS | 200 |
| `POST /stores/{id}/disable` | PASS | 200（status=disabled） |

鉴权：普通用户访问 `/stores` → 403（实测）。

## 7. 数据库验收（§49）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 全新/增量 Migration | PASS | `0001_baseline` → `0002_platform_stores` 执行成功 |
| 凭据加密落库 | PASS | `credentials_encrypted` 列存 Fernet 密文；API 仅返回 `credentials_masked` |
| Index | PASS | `ix_platform_stores_platform` |
| Rollback | PASS | `downgrade()` 删除索引与表 |

## 8. Connector 验收（§40）

见第 4 节；结论 `REAL_INTEGRATION: NOT_VERIFIED`。

## 9. Finance 验收（§41）

`NOT_IMPLEMENTED` — Phase 5。

## 10. AI / Agent 验收（§43、§44）

`NOT_IMPLEMENTED` — Phase 6/7。

## 11. RAG 验收（§45）

`NOT_IMPLEMENTED` — Phase 8。

## 12. Worker 验收（§46）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Task 创建 / 消费 / 状态查询 | PASS | 回归通过（Phase 1 证据） |
| 同步任务注册 | PASS | `sync.products` 入队 202；未配置平台时任务失败可见 |

## 13. Security 检查（§50）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Secret 不进入 Git | PASS | `STORE_CREDENTIAL_KEY` 仅存于 `.env`（已 ignore） |
| Credential 不写日志 | PASS | 凭据仅在解密时使用，不落日志 |
| Credential 不返回前端 | PASS | 响应仅含脱敏值（实测响应体不含明文） |
| 缺失密钥可操作报错 | PASS | `CredentialCipherError` 提示生成 Fernet 密钥的命令 |
| 敏感 API 权限 | PASS | 店铺/Connector 接口需管理员 |

## 14. Regression Test（§51）

```text
docs/evidence/phase4/02_pytest.txt: 44 passed
```

Phase 1–4 全部测试通过，无回归。

## 15. E2E 验收（§52）

```text
管理员登录 → 创建 Store（凭据加密）→ 平台列表显示 shopify(configured=False)
  → 未配置时同步被拒（409，标注 NOT_VERIFIED）
  → Fake Shopify Sandbox 可达
  → Connector 单测覆盖 token 失效/限流/平台异常/网络错误/分页/空数据/字段缺失/重复同步/中断续跑
```

## 16. 测试数量与结果

| 类型 | 数量 | 结果 |
| --- | --- | --- |
| Unit / API Test（pytest） | 44 | PASS |
| Acceptance（Sandbox + 真实 Saleor，脚本） | 10 项 | PASS |

## 17. 已知问题

13. **真实平台凭据缺失** — `REAL_INTEGRATION: NOT_VERIFIED`；配置 `SHOPIFY_SHOP_DOMAIN`/`SHOPIFY_ACCESS_TOKEN` 后即可执行真实同步。
14. **Shopify 库存接口复用商品接口** — `get_inventory` 目前从商品变体读取库存；独立 InventoryLevel API 待真实店铺接入后按需替换。
15. **同步为单向（平台 → Saleor）** — 回写平台（create_product/update_inventory 等）接口已在 `EcommerceConnector` 声明，Shopify 侧实现待 Phase 10 前补齐。

## 18. 未完成功能

- 店铺管理前端页面
- 订单同步任务（`sync.orders`）
- Shopify 侧写回（创建/更新商品、更新库存）
- 真实平台凭据接入与验证

## 19. Blocked 项

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 真实 Shopify 集成验证 | BLOCKED | 需要真实店铺域名与 Admin API token（外部资源） |

已按 spec §55 记录：

```text
Blocked Reason: 无真实 Shopify 店铺凭据
Required External Resource: SHOPIFY_SHOP_DOMAIN + SHOPIFY_ACCESS_TOKEN
Already Verified Parts: Connector 代码、错误路径、幂等、Store 凭据加密、Sandbox 全链路
Unverified Parts: 真实平台数据读写
How To Continue Verification: 在 .env 配置凭据 → POST /connectors/shopify/sync/products
```

## 20. 最终状态

```text
PASS
```

（平台真实集成项单独标注 BLOCKED，未计入 PASS。）

---

# Phase 5 — Finance

> 状态：PASS。

## 1. Build 信息

| 项 | 值 |
| --- | --- |
| Phase | Phase 5 — Finance（独立领域） |
| 日期 | 2026-09-20 |
| 方案 | Finance 作为独立 Domain 自建表（不复用 Saleor 订单字段做记账）；金额统一 `Decimal` + 币种精度 + half-up 舍入；幂等键唯一约束；Webhook HMAC 验签 |
| 新增代码 | `modules/finance/{domain,application,api,repository}`、Alembic `0003_finance` |
| 核心表 | `payments`、`payment_transactions`、`refunds`、`refund_transactions`、`settlements`、`settlement_items`、`reconciliations`、`finance_ledger` |

## 2. Git Commit SHA

```text
见提交：feat(finance): 支付/退款/结算/对账（幂等 + Decimal + 验签）
```

## 3. 运行环境

同 Phase 1；新增 `PAYMENT_WEBHOOK_SECRET`（必填）。

## 4. 功能验收（§41）

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 正常支付 | PASS | payment created -> 201 |
| 支付失败（金额非法/为零） | PASS | zero amount rejected -> 422 |
| 重复支付请求 | PASS | 同一 Idempotency Key 请求 4 次 → 仅 1 笔交易（`created=false`） |
| 重复 Webhook | PASS | duplicate=True，且 payment 记录仅 1 条 |
| 非法 Webhook 签名 | PASS | invalid webhook signature -> 401 |
| 全额退款 | PASS | 累计 refunded=100.00 |
| 部分退款 | PASS | partial refund -> 201（30.00） |
| 重复退款 | PASS | 同 key → created=false，无新交易 |
| 超额退款 | PASS | over refund rejected -> 409 |
| 结算 | PASS | gross=1500.00 |
| 手续费（平台/支付） | PASS | platform_fee=75.00（5%）、payment_fee=30.00（2%） |
| 多币种 | PASS | JPY 支付 amount=1000（0 位小数） |
| 汇率 | NOT_IMPLEMENTED | 当前为单币种结算；汇率换算表待 Phase 9 利润分析时引入 |
| 对账差异 | PASS | matched（diff=0.00）/ mismatched（diff=-5.00） |

核心约束验证（spec §41）：

```text
同一 Idempotency Key → 重复请求 N 次 → 只能产生一次有效交易   ✅ 实测
累计退款金额 <= 可退款金额                                  ✅ 实测（超限 409）
```

金额处理：

| 规则 | 状态 | 说明 |
| --- | --- | --- |
| 禁止 float | PASS | `to_decimal` 对 float 直接抛 `MoneyError`（单测） |
| Decimal / 明确 currency | PASS | 所有金额列 `Numeric(18,4)`，接口按币种精度输出 |
| 明确 rounding | PASS | `ROUND_HALF_UP`，按 ISO 4217 exponent 量化（USD 2 位 / JPY 0 位） |

可追溯性：

| 项 | 状态 | 证据 |
| --- | --- | --- |
| Transaction ID | PASS | `payment_transactions.external_id` / `refund_transactions.external_id` |
| 时间 | PASS | `created_at`（timezone-aware） |
| 来源 | PASS | `source`（api / webhook） |
| 状态变化记录 | PASS | 支付/退款/结算状态列 |
| Audit Log | PASS | `finance_ledger`（payment/refund/settlement 三类分录，实测） |

## 5. 前端验收（§47）

`NOT_IMPLEMENTED` — 财务页面属 Phase 9 Dashboard 范围。

## 6. API 验收（§48）

| 接口 | 状态 | 说明 |
| --- | --- | --- |
| `POST /finance/payments` | PASS | 201；幂等；金额非法 422 |
| `GET /finance/payments` / `{id}` | PASS | 200；不存在 404 |
| `POST /finance/refunds` | PASS | 201；超额 409；幂等 |
| `GET /finance/refunds` | PASS | 200 |
| `POST /finance/settlements` | PASS | 201（自动汇总费用与净额） |
| `GET /finance/settlements` | PASS | 200 |
| `POST /finance/reconciliations` | PASS | 201（matched / mismatched） |
| `GET /finance/ledger` | PASS | 200 |
| `POST /finance/webhooks/{provider}` | PASS | 验签失败 401；负载非法 422；重复 200+duplicate |

鉴权：普通用户访问财务接口 → 403（实测）。

## 7. 数据库验收（§49）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| Migration（增量） | PASS | `0002 → 0003_finance` 执行成功 |
| Unique Constraint | PASS | `uq_payments_idempotency_key`、`uq_refunds_idempotency_key` |
| Foreign Key | PASS | transactions/refunds/settlement_items → 父表 |
| Index | PASS | order_ref / payment_id / settlement_id / reference |
| Decimal 精度 | PASS | `docs/evidence/phase5/02_db_decimal_check.txt`（Numeric(18,4) 精确保存） |
| Transaction 正确性 | PASS | 幂等冲突依赖唯一约束，重复请求返回既有记录 |
| Rollback | PASS | `downgrade()` 逆序删除全部表 |

## 8. Connector 验收（§40）

`REAL_INTEGRATION: NOT_VERIFIED`（见 Phase 4）。支付侧目前为自建 Finance 领域 + Webhook 验签，未接真实支付网关。

## 9. Finance 验收（§41）

见第 4 节：全部必测项 PASS（汇率换算除外，标注 NOT_IMPLEMENTED）。

## 10. AI / Agent 验收（§43、§44）

`NOT_IMPLEMENTED` — Phase 6/7。

## 11. RAG 验收（§45）

`NOT_IMPLEMENTED` — Phase 8。

## 12. Worker 验收（§46）

本 Phase 未新增 Worker 任务；回归通过。

## 13. Security 检查（§50）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Webhook 验签 | PASS | HMAC-SHA256 + `compare_digest`；非法签名 401 |
| 密钥不入库/不入日志 | PASS | `PAYMENT_WEBHOOK_SECRET` 来自环境变量 |
| 敏感 API 权限 | PASS | 财务接口需管理员（403 实测） |
| 幂等防重放 | PASS | Webhook 事件 id 派生的幂等键 |

## 14. Regression Test（§51）

```text
docs/evidence/phase5/03_pytest.txt: 56 passed
```

Phase 1–5 全部通过，无回归。

## 15. E2E 验收（§52）

```text
登录 → 创建支付（幂等）→ 部分退款 → 重复退款（幂等）→ 超额退款被拒
     → 补齐全额退款 → 累计退款额正确
     → Webhook 验签失败被拒 / 成功处理 / 重复投递无二次副作用
     → 结算（费用与净额）→ 对账 matched / mismatched
     → 多币种（JPY）→ Ledger 可追溯 → 普通用户 403
```

## 16. 测试数量与结果

| 类型 | 数量 | 结果 |
| --- | --- | --- |
| Unit / API Test（pytest） | 56 | PASS |
| Acceptance（真实 PostgreSQL + HTTP，脚本） | 18 项 | PASS |

## 17. 已知问题

16. **汇率为 NOT_IMPLEMENTED** — 结算与利润目前按单币种处理，跨币种换算待 Phase 9 引入汇率表。
17. **支付网关为自建记账** — 未接 Stripe/PayPal Sandbox；`Payment Connector` 接口（spec §11）尚未实现具体 Provider。
18. **对账为手工触发** — 自动定时对账（Worker）待 Phase 10 补充。

## 18. 未完成功能

- Payment Connector（Stripe/PayPal Sandbox）
- 汇率与多币种换算
- 财务前端页面
- 自动对账 Worker 任务

## 19. Blocked 项

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 真实支付网关验证 | BLOCKED | 需要 Stripe/PayPal Sandbox 账号与 API Key（外部资源） |

```text
Blocked Reason: 无支付 Sandbox 凭据
Required External Resource: STRIPE_SECRET_KEY（或等价）
Already Verified Parts: 记账、幂等、退款上限、验签、结算、对账、精度、审计
Unverified Parts: 与真实支付网关的交互与回调
How To Continue Verification: 配置 Sandbox 密钥后接入 Payment Connector 并重跑验收
```

## 20. 最终状态

```text
PASS
```

（真实支付网关项单独标注 BLOCKED，未计入 PASS。）
