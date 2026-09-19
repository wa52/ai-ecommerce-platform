"""内置业务工具（spec §15、§17）：Commerce / Finance / Analytics 能力。

工具只读取真实业务数据；失败必须显式返回错误，禁止让模型猜测数据（spec §44）。
"""

import logging

from app.connectors.factory import get_commerce_adapter
from app.modules.ai.tools.base import Tool, ToolContext, ToolExecutionError, ToolResult
from app.modules.commerce.application.service import CommerceError, CommerceService

logger = logging.getLogger(__name__)


class _CommerceTool(Tool):
    requires_admin = True

    def _service(self, ctx: ToolContext) -> CommerceService:
        return CommerceService(get_commerce_adapter(), token=ctx.token)


class SearchProductsTool(_CommerceTool):
    name = "commerce.search_products"
    description = "按关键词或 slug 搜索商品，返回统一商品模型列表。"
    parameters = {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "关键词（可选）"},
            "slug": {"type": "string", "description": "精确 slug（可选）"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
    }

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        limit = int(arguments.get("limit", 10))
        try:
            items, page = await self._service(ctx).list_products(
                search=arguments.get("search"), slug=arguments.get("slug"), first=limit, after=None
            )
        except CommerceError as exc:
            return ToolResult(ok=False, error=str(exc))
        return ToolResult(
            ok=True,
            data={
                "total_count": page.total_count,
                "items": [p.model_dump() for p in items],
            },
        )


class RecentOrdersTool(_CommerceTool):
    name = "commerce.recent_orders"
    description = "查询最近订单（含条目、金额、币种、状态）。"
    parameters = {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "渠道 ID（可选）"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
    }

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        limit = int(arguments.get("limit", 10))
        try:
            items, page = await self._service(ctx).list_orders(
                channel=arguments.get("channel_id"), first=limit, after=None
            )
        except CommerceError as exc:
            return ToolResult(ok=False, error=str(exc))
        return ToolResult(
            ok=True,
            data={
                "total_count": page.total_count,
                "items": [
                    {
                        "number": o.number,
                        "status": o.status,
                        "payment_status": o.payment_status,
                        "total_amount": o.total_amount,
                        "currency": o.currency,
                        "items": len(o.items),
                    }
                    for o in items
                ],
            },
        )


class FinanceSummaryTool(Tool):
    name = "finance.summary"
    description = "汇总支付/退款/结算金额（按币种），用于财务分析。"
    requires_admin = True
    parameters = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 200}},
    }

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.infrastructure.config.settings import get_settings
        from app.modules.finance.application.service import FinanceService

        session_factory = ctx.extra.get("session_factory")
        engine = None
        if session_factory is None:
            engine = create_async_engine(str(get_settings().database_url))
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with session_factory() as session:
                service = FinanceService(session)
                payments = await service.list_payments(limit=int(arguments.get("limit", 200)))
                refunds = await service.list_refunds(limit=int(arguments.get("limit", 200)))
                settlements = await service.list_settlements(limit=int(arguments.get("limit", 200)))
        except Exception as exc:  # noqa: BLE001 - 显式转为工具失败
            logger.warning("finance summary tool failed: %s", type(exc).__name__)
            return ToolResult(ok=False, error=f"财务数据查询失败：{type(exc).__name__}")
        finally:
            if engine is not None:
                await engine.dispose()

        by_currency: dict[str, dict] = {}
        for p in payments:
            bucket = by_currency.setdefault(
                p.currency, {"paid": "0", "refunded": "0", "settled_net": "0", "payments": 0, "refunds": 0}
            )
            bucket["payments"] += 1
            bucket["paid"] = f"{float(bucket['paid']) + float(p.amount):.2f}"
        for r in refunds:
            bucket = by_currency.setdefault(
                r.currency, {"paid": "0", "refunded": "0", "settled_net": "0", "payments": 0, "refunds": 0}
            )
            bucket["refunds"] += 1
            bucket["refunded"] = f"{float(bucket['refunded']) + float(r.amount):.2f}"
        for s in settlements:
            bucket = by_currency.setdefault(
                s.currency, {"paid": "0", "refunded": "0", "settled_net": "0", "payments": 0, "refunds": 0}
            )
            bucket["settled_net"] = f"{float(bucket['settled_net']) + float(s.net_amount):.2f}"

        if not payments and not refunds and not settlements:
            return ToolResult(ok=True, data={"by_currency": {}, "note": "暂无财务数据"})
        return ToolResult(ok=True, data={"by_currency": by_currency})


class SalesSummaryTool(_CommerceTool):
    name = "analytics.sales_summary"
    description = "基于真实订单计算销售额、订单量、客单价（按币种）。"
    parameters = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}},
    }

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        limit = int(arguments.get("limit", 50))
        try:
            orders, page = await self._service(ctx).list_orders(channel=None, first=limit, after=None)
        except CommerceError as exc:
            return ToolResult(ok=False, error=str(exc))

        if not orders:
            return ToolResult(ok=True, data={"order_count": 0, "note": "暂无订单数据"})

        by_currency: dict[str, dict] = {}
        for o in orders:
            bucket = by_currency.setdefault(o.currency, {"orders": 0, "gross": "0.00"})
            bucket["orders"] += 1
            bucket["gross"] = f"{float(bucket['gross']) + float(o.total_amount):.2f}"

        for currency, bucket in by_currency.items():
            bucket["avg_order_value"] = f"{float(bucket['gross']) / bucket['orders']:.2f}"

        return ToolResult(
            ok=True,
            data={"sampled_orders": len(orders), "total_count": page.total_count, "by_currency": by_currency},
        )


class RagSearchTool(Tool):
    """Agent 的 RAG 能力（spec §16：RAG 只是 Agent 可调用的一种能力）。"""

    name = "rag.search"
    description = "在指定知识库中检索资料片段（返回片段、来源与分数）。"
    requires_admin = True
    parameters = {
        "type": "object",
        "properties": {
            "knowledge_base_id": {"type": "string", "description": "知识库 ID"},
            "query": {"type": "string", "description": "检索问题"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
        "required": ["knowledge_base_id", "query"],
    }

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.infrastructure.config.settings import get_settings
        from app.modules.ai.rag.embeddings import build_embedding_provider
        from app.modules.ai.rag.service import RagError, RagService

        kb_id = arguments.get("knowledge_base_id")
        query = arguments.get("query")
        if not kb_id or not query:
            return ToolResult(ok=False, error="缺少参数 knowledge_base_id 或 query")

        session_factory = ctx.extra.get("session_factory")
        engine = None
        if session_factory is None:
            engine = create_async_engine(str(get_settings().database_url))
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with session_factory() as session:
                service = RagService(session, build_embedding_provider(get_settings()))
                chunks = await service.retrieve(
                    kb_id=kb_id, query=query, top_k=int(arguments.get("top_k", 5))
                )
        except RagError as exc:
            return ToolResult(ok=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("rag tool failed: %s", type(exc).__name__)
            return ToolResult(ok=False, error=f"知识库检索失败：{type(exc).__name__}")
        finally:
            if engine is not None:
                await engine.dispose()

        if not chunks:
            return ToolResult(ok=True, data={"count": 0, "chunks": [], "note": "知识库中没有相关资料"})
        return ToolResult(ok=True, data={"count": len(chunks), "chunks": [c.as_dict() for c in chunks]})


class ToolFailureProbeTool(Tool):
    """用于验收工具失败路径（Phase 7 acceptance）。"""

    name = "debug.always_fails"
    description = "始终失败的工具，用于验证 Tool Failure 处理。"
    parameters = {"type": "object", "properties": {}}

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        return ToolResult(ok=False, error="模拟工具失败")


class AdminOnlyProbeTool(Tool):
    name = "debug.admin_only"
    description = "仅管理员可用的工具，用于验证权限约束。"
    requires_admin = True
    parameters = {"type": "object", "properties": {}}

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        return ToolResult(ok=True, data={"user": ctx.user.email, "is_admin": ctx.is_admin})
