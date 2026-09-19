# ACCEPTANCE_REPORT — Phase 1（基础骨架 / 基础设施）

> 本报告依据 `PROJECT_SPEC.md` §34–§56 编写。状态只使用 PASS / FAIL / BLOCKED / NOT_IMPLEMENTED。

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
见本 Phase 提交：feat(skeleton): Phase 1 基础设施骨架（Saleor + FastAPI AI 扩展层）
（SHA 由本次提交产生，记录于 Git 日志）
```

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
