"""
MVP 版 Agent。

它先用规则做意图路由，再调用 typed skill。若配置了 DeepSeek/Qwen API key，
会把结构化结果交给 LLM 生成更自然的解释；未配置时使用本地模板。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.agent.llm_factory import get_llm
from app.config import get_settings
from app.data.akshare_fund import get_latest_fund_quote
from app.data.akshare_news import get_us_market_snapshot
from app.data.akshare_sector import get_sector_news, get_sector_overview
from app.database import async_session
from app.models.portfolio import PortfolioItem
from app.rag.service import format_rag_context, retrieve_knowledge
from app.skills.registry import skill_registry
from sqlalchemy import select


CODE_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def _extract_codes(message: str) -> list[str]:
    seen: set[str] = set()
    codes: list[str] = []
    for code in CODE_PATTERN.findall(message):
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _detect_fund_type(message: str) -> str:
    upper = message.upper()
    if "QDII" in upper or "纳斯达克" in message or "标普" in message or "海外" in message:
        return "QDII"
    if "债" in message:
        return "债券型"
    if "指数" in message or "ETF" in upper:
        return "指数型"
    if "股票" in message:
        return "股票型"
    if "混合" in message:
        return "混合型"
    return "全部"


def _detect_risk(message: str) -> str:
    if any(word in message for word in ["稳健", "低风险", "保守", "回撤小"]):
        return "conservative"
    if any(word in message for word in ["激进", "高收益", "进取", "弹性"]):
        return "aggressive"
    return "balanced"


def _detect_top_n(message: str, default: int = 5) -> int:
    digit_match = re.search(r"(\d+)\s*[只个支]?", message)
    if digit_match:
        return max(1, min(10, int(digit_match.group(1))))
    chinese_numbers = {
        "一": 1,
        "两": 2,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    for word, value in chinese_numbers.items():
        if f"{word}只" in message or f"{word}个" in message or f"{word}支" in message:
            return value
    return default


def _is_market_analysis_intent(message: str) -> bool:
    keywords = [
        "市场",
        "大盘",
        "行情",
        "资金",
        "流入",
        "流出",
        "抄底",
        "见底",
        "杀跌",
        "普跌",
        "回调",
        "下跌",
        "大跌",
        "A股",
        "港股",
        "恒科",
        "恒生科技",
        "特朗普",
        "现状",
        "利好",
        "利空",
        "趋势",
        "大趋势",
        "政策",
        "供需",
        "美股",
        "纳指",
        "标普",
        "当天",
        "今日",
        "今天",
        "短线",
        "中线",
        "长线",
        "操作",
        "加仓",
        "减仓",
        "定投",
        "转换",
        "止盈",
        "止损",
        "怎么看",
        "分析",
    ]
    return any(word in message for word in keywords)


def _is_market_based_request(message: str) -> bool:
    if any(word in message for word in [
        "基于今天",
        "今天的市场",
        "今天市场",
        "今日市场",
        "今日的市场",
        "当日市场",
        "当前市场",
        "市场环境",
        "市场如何",
        "行情",
        "大盘",
        "快讯",
        "资金",
        "抄底",
        "见底",
        "普跌",
    ]):
        return True
    return any(word in message for word in ["基于今天", "今天的市场", "今天市场", "今日市场", "今日的市场", "当日市场", "当前市场", "市场环境", "行情", "大盘", "快讯"])


def _is_sector_analysis_intent(message: str) -> bool:
    sector_words = ["板块", "行业", "半导体", "电池", "电网", "设备", "光伏", "新能源", "机器人", "算力", "通信", "传媒", "医药"]
    return any(word in message for word in sector_words)


def _wants_recommendation(message: str) -> bool:
    return any(word in message for word in ["推荐", "选", "买", "候选", "配置"])


def _is_portfolio_intent(message: str) -> bool:
    return any(word in message for word in ["我的", "组合", "持仓", "仓位", "收益", "盈亏", "亏损", "盈利", "浮盈", "浮亏"])


def _should_attach_portfolio_context(message: str) -> bool:
    return (
        _is_portfolio_intent(message)
        or _is_market_analysis_intent(message)
        or _is_market_based_request(message)
        or _is_sector_analysis_intent(message)
    )


SECTOR_ALIASES: dict[str, list[str]] = {
    "半导体": ["半导体", "芯片", "集成电路"],
    "半导体设备": ["半导体", "专用设备", "电子化学品", "光学光电子"],
    "电网": ["电网设备", "电力设备", "特高压", "智能电网"],
    "电池": ["电池", "能源金属", "锂电池", "新能源车"],
    "光伏": ["光伏设备", "电力设备"],
    "通信": ["通信设备", "通信服务"],
    "算力": ["通信设备", "计算机设备", "软件开发"],
}


def _llm_configured(provider: str | None = None) -> bool:
    settings = get_settings()
    active = (provider or settings.ACTIVE_LLM).lower()
    if active == "moonshot":
        active = "kimi"
    keys = {
        "deepseek": settings.DEEPSEEK_API_KEY,
        "qwen": settings.QWEN_API_KEY,
        "kimi": settings.KIMI_API_KEY,
    }
    key = keys.get(active, "")
    return bool(key and not key.startswith("sk-your") and "your-" not in key)


def _format_history(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return "无"
    lines: list[str] = []
    for item in history[-8:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role}: {content[:800]}")
    return "\n".join(lines) or "无"


def _plain_text_response(text: str) -> str:
    """把模型常见 Markdown 语法清掉，前端按纯文本投研纪要展示。"""
    if not text:
        return text
    cleaned = text.replace("```", "")
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"^\s*[-*+]\s+", "· ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*>+\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


async def _retrieve_rag_context(message: str) -> list[dict[str, Any]]:
    async with async_session() as session:
        chunks = await retrieve_knowledge(session, message, top_k=8)
        project_words = ["项目", "功能", "规划", "架构", "前端", "后端", "RAG", "知识库"]
        if any(word in message for word in project_words):
            return chunks[:5]
        return [chunk for chunk in chunks if chunk.get("category") != "project_research"][:5]


async def _build_sector_context(message: str) -> dict[str, Any]:
    overview = await get_sector_overview(limit=120)
    sectors = overview.get("sectors", [])
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for label, aliases in SECTOR_ALIASES.items():
        if label not in message and not any(alias in message for alias in aliases):
            continue
        for sector in sectors:
            name = str(sector.get("name", ""))
            if any(alias in name for alias in aliases):
                key = name or label
                if key not in seen:
                    seen.add(key)
                    row = dict(sector)
                    row["matched_label"] = label
                    selected.append(row)
    if not selected and _is_sector_analysis_intent(message):
        selected = list((overview.get("recommended") or sectors[:6])[:6])

    news_by_sector: dict[str, Any] = {}
    for sector in selected[:4]:
        name = str(sector.get("name") or "")
        if not name:
            continue
        news_by_sector[name] = await get_sector_news(name, limit=5)

    return {
        "overview": {
            "as_of": overview.get("as_of"),
            "source": overview.get("source"),
            "flow_summary": overview.get("flow_summary"),
            "warnings": overview.get("warnings", []),
        },
        "selected": selected[:8],
        "recommended": (overview.get("recommended") or [])[:6],
        "risk_alerts": (overview.get("risk_alerts") or [])[:6],
        "news_by_sector": news_by_sector,
    }


def _estimate_daily_profit(amount: float | None, daily_return: float | None) -> float | None:
    if amount is None or daily_return is None:
        return None
    rate = daily_return / 100
    if rate <= -0.999999:
        return None
    return round(float(amount) * rate / (1 + rate), 2)


def _snapshot_date_from_source(source: str | None) -> str | None:
    if not source:
        return None
    if source.startswith("screenshot_"):
        raw = source.removeprefix("screenshot_").replace("_", "-")
        return raw if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) else None
    return None


async def _build_portfolio_context(fetch_quotes: bool = True) -> dict[str, Any]:
    async with async_session() as session:
        rows = (await session.execute(select(PortfolioItem))).scalars().all()
    holdings = [item for item in rows if item.is_holding]
    total_amount = round(sum(float(item.amount or 0) for item in holdings), 2)

    semaphore = asyncio.Semaphore(5)

    async def load_quote(item: PortfolioItem) -> tuple[int, dict[str, Any]]:
        if not item.fund_code:
            return item.id, {}
        async with semaphore:
            try:
                quote = await get_latest_fund_quote(item.fund_code)
            except Exception as exc:
                quote = {
                    "source": "error",
                    "error": str(exc),
                    "snapshot_daily_profit": item.yesterday_profit,
                    "snapshot_date": _snapshot_date_from_source(item.source),
                }
            quote["estimated_daily_profit"] = _estimate_daily_profit(item.amount, quote.get("daily_return"))
            return item.id, quote

    if fetch_quotes and holdings:
        quotes = dict(await asyncio.gather(*(load_quote(item) for item in holdings)))
        quote_source = "portfolio_items + latest_nav"
    else:
        quotes = {
            item.id: {
                "snapshot_daily_profit": item.yesterday_profit,
                "snapshot_date": _snapshot_date_from_source(item.source),
                "daily_return": None,
                "nav_date": None,
                "source": "imported_portfolio_snapshot",
            }
            for item in holdings
        }
        quote_source = "portfolio_items + imported_snapshot"
    daily_values = [
        quote.get("estimated_daily_profit")
        for quote in quotes.values()
        if quote.get("estimated_daily_profit") is not None
    ]
    snapshot_values = [
        quote.get("snapshot_daily_profit")
        for quote in quotes.values()
        if quote.get("snapshot_daily_profit") is not None
    ]
    snapshot_dates = [
        quote.get("snapshot_date")
        for quote in quotes.values()
        if quote.get("snapshot_date")
    ]
    estimated_daily_profit = round(sum(float(value) for value in daily_values), 2) if daily_values else None
    previous_total = total_amount - estimated_daily_profit if estimated_daily_profit is not None else None
    snapshot_daily_profit = round(sum(float(value) for value in snapshot_values), 2) if snapshot_values else None
    snapshot_previous_total = total_amount - snapshot_daily_profit if snapshot_daily_profit is not None else None
    qdii_amount = 0.0
    theme_amount = 0.0
    positions: list[dict[str, Any]] = []
    for item in holdings:
        tags = item.tags or []
        amount = float(item.amount or 0)
        if "QDII" in tags:
            qdii_amount += amount
        if "行业主题" in tags:
            theme_amount += amount
        quote = quotes.get(item.id, {})
        positions.append(
            {
                "fund_code": item.fund_code,
                "fund_name": item.fund_name,
                "amount": round(amount, 2),
                "position_pct": round(amount / total_amount * 100, 2) if total_amount else 0.0,
                "holding_profit": item.holding_profit,
                "holding_return_pct": item.holding_return_pct,
                "nav_daily_return": quote.get("daily_return"),
                "estimated_daily_profit": quote.get("estimated_daily_profit"),
                "snapshot_daily_profit": quote.get("snapshot_daily_profit"),
                "snapshot_date": quote.get("snapshot_date"),
                "nav_date": quote.get("nav_date"),
                "tags": tags,
            }
        )
    positions.sort(key=lambda row: row["amount"], reverse=True)
    return {
        "total_amount": total_amount,
        "holding_count": len(holdings),
        "watchlist_count": len([item for item in rows if item.is_watchlist and not item.is_holding]),
        "estimated_daily_profit": estimated_daily_profit,
        "estimated_daily_return_pct": round(estimated_daily_profit / previous_total * 100, 4)
        if estimated_daily_profit is not None and previous_total else None,
        "snapshot_daily_profit": snapshot_daily_profit,
        "snapshot_daily_return_pct": round(snapshot_daily_profit / snapshot_previous_total * 100, 4)
        if snapshot_daily_profit is not None and snapshot_previous_total else None,
        "snapshot_covered_count": len(snapshot_values),
        "snapshot_date": max(snapshot_dates) if snapshot_dates else None,
        "quote_covered_count": len(daily_values),
        "qdii_amount": round(qdii_amount, 2),
        "qdii_pct": round(qdii_amount / total_amount * 100, 2) if total_amount else 0.0,
        "theme_amount": round(theme_amount, 2),
        "theme_pct": round(theme_amount / total_amount * 100, 2) if total_amount else 0.0,
        "top_positions": positions[:10],
        "source": quote_source,
    }


def _portfolio_text(context: dict[str, Any]) -> str:
    lines = [
        "我可以读取你当前录入的持仓、仓位、持有收益和已导入的快照盈亏；只有拿到实时净值时才会标记为当日估算。",
        f"当前持仓市值约 {context.get('total_amount', 0):.2f}，持有 {context.get('holding_count', 0)} 只，观察池 {context.get('watchlist_count', 0)} 只。",
    ]
    if context.get("estimated_daily_profit") is not None:
        lines.append(
            f"按实时净值估算，当日盈亏 {context['estimated_daily_profit']:+.2f}，组合净值涨跌 {_format_pct(context.get('estimated_daily_return_pct'))}。"
        )
    elif context.get("snapshot_daily_profit") is not None:
        snapshot_date = context.get("snapshot_date") or "导入日"
        lines.append(
            f"当前没有实时净值，以下盈亏来自 {snapshot_date} 的导入快照：快照日盈亏 {context['snapshot_daily_profit']:+.2f}，快照涨跌 {_format_pct(context.get('snapshot_daily_return_pct'))}。"
        )
    lines.append(f"QDII 仓位 {_format_pct(context.get('qdii_pct'))}，行业主题仓位 {_format_pct(context.get('theme_pct'))}。")
    for item in context.get("top_positions", [])[:5]:
        profit = item.get("estimated_daily_profit")
        profit_label = "估算盈亏"
        if profit is None and item.get("snapshot_daily_profit") is not None:
            profit = item.get("snapshot_daily_profit")
            profit_label = f"快照盈亏({item.get('snapshot_date') or '导入日'})"
        lines.append(
            f"{item.get('fund_name')}：占比 {_format_pct(item.get('position_pct'))}，"
            f"当日净值涨跌 {_format_pct(item.get('nav_daily_return'))}，{profit_label} {profit if profit is not None else '暂无'}。"
        )
    return "\n".join(lines)


async def _polish_with_llm(
    message: str,
    data: dict[str, Any],
    fallback: str,
    history: list[dict[str, Any]] | None = None,
    system_hint: str = "",
    deep_mode: bool = False,
    model_provider: str | None = None,
) -> str:
    if not _llm_configured(model_provider):
        return _plain_text_response(fallback)
    prompt = (
        "你是面向中国 A 股和公募基金个人投资者的投研助手。"
        "基于给定 JSON 数据，用中文输出简洁、可执行、不过度承诺的分析。"
        "可以给出候选和倾向，但必须说明数据来源、风险、为什么需要复核。"
        "不要编造 JSON 中不存在的实时数据。"
        "禁止使用 Markdown 格式：不要输出标题符号、星号加粗、代码块、表格或 Markdown 列表。"
        "请用中文短段落、中文序号和清晰小标题表达。"
        + (
            "当前为深度问策模式。请先梳理证据链，再给结论；必须覆盖支持证据、反向证据、关键不确定性、短线与长线分歧、仓位动作和复核清单。"
            if deep_mode else ""
        )
        + f"{system_hint}\n\n"
        f"最近上下文：\n{_format_history(history)}\n\n"
        f"知识库检索片段：\n{format_rag_context(data.get('rag_context', []))}\n\n"
        f"用户问题：{message}\n\n"
        f"结构化数据：{json.dumps(data, ensure_ascii=False)[:12000]}"
    )
    try:
        llm = get_llm(purpose="reasoner" if deep_mode else "chat", provider=model_provider)
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=90 if deep_mode else 25)
        content = getattr(response, "content", "")
        return _plain_text_response(content) if isinstance(content, str) and content.strip() else _plain_text_response(fallback)
    except Exception:
        return _plain_text_response(fallback)


def _format_pct(value: Any) -> str:
    if value is None:
        return "暂无"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _recommend_text(data: dict[str, Any]) -> str:
    funds = data.get("funds", [])
    if not funds:
        return "我没有拿到足够的基金数据。可以换一个基金类型，或稍后等数据源恢复后再试。"
    lines = [
        f"我先按 {data.get('fund_type', '基金')} 和 {data.get('risk_preference', 'balanced')} 风险偏好筛出 {len(funds)} 个初筛对象。",
        "这不是黑箱预测，而是用多周期收益指标、风险约束和可复核数据做初筛，再把回撤、费率、持仓和溢价留给下一步复核。",
    ]
    for index, fund in enumerate(funds, start=1):
        lines.append(
            f"{index}. {fund.get('name')}（{fund.get('code')}）：评分 {fund.get('score')}，"
            f"近1年 {_format_pct(fund.get('year_return'))}，近6月 {_format_pct(fund.get('six_month_return'))}，"
            f"风险 {fund.get('risk_level', '中等')}。"
        )
    if data.get("warning"):
        lines.append(data["warning"])
    lines.append("下一步建议打开详情页看净值回撤、持仓集中度和申购费率，再决定是否加入自选。")
    return "\n".join(lines)


async def _market_based_recommendation(
    message: str,
    top_n: int,
    history: list[dict[str, Any]] | None,
    deep_mode: bool = False,
    model_provider: str | None = None,
) -> dict[str, Any]:
    explicit_type = _detect_fund_type(message)
    risk = _detect_risk(message)
    fund_types = [explicit_type] if explicit_type != "全部" else ["指数型", "混合型", "债券型", "QDII"]
    if explicit_type == "全部" and any(word in message.upper() for word in ["美股", "海外", "纳指", "纳斯达克", "标普", "QDII"]):
        fund_types = ["QDII", "指数型", "混合型", "债券型"]

    funds: list[dict[str, Any]] = []
    skills_used: list[str] = []
    skill = skill_registry.get("fund_recommend")
    for fund_type in fund_types:
        result = await skill.run(fund_type=fund_type, risk_preference=risk, top_n=max(2, top_n))
        skills_used.append(skill.name)
        for fund in (result.data or {}).get("funds", []):
            row = dict(fund)
            row["source_bucket"] = fund_type
            funds.append(row)

    seen: set[str] = set()
    diversified: list[dict[str, Any]] = []
    for preferred_type in fund_types:
        bucket_items = [item for item in funds if item.get("source_bucket") == preferred_type]
        bucket_items.sort(key=lambda item: item.get("score", 0), reverse=True)
        for item in bucket_items[:1]:
            code = item.get("code")
            if code and code not in seen:
                seen.add(code)
                diversified.append(item)
        if len(diversified) >= top_n:
            break
    for item in sorted(funds, key=lambda row: row.get("score", 0), reverse=True):
        code = item.get("code")
        if code and code not in seen:
            seen.add(code)
            diversified.append(item)
        if len(diversified) >= top_n:
            break

    news_skill = skill_registry.get("news_fetch")
    news_result = await news_skill.run(limit=20)
    skills_used.append(news_skill.name)
    data = {
        "fund_type": explicit_type,
        "risk_preference": risk,
        "count": len(diversified[:top_n]),
        "funds": diversified[:top_n],
        "market_news": news_result.data or {},
        "method": "先读取今日市场快讯，再跨基金类型做分散初筛；除非用户明确要求 QDII，不默认只推荐 QDII。",
    }
    data["rag_context"] = await _retrieve_rag_context(message)
    if _should_attach_portfolio_context(message):
        data["portfolio_context"] = await _build_portfolio_context()
    if any(word in message.upper() for word in ["QDII", "美股", "纳指", "纳斯达克", "标普", "海外"]):
        data["us_market"] = await get_us_market_snapshot(limit=12)
        skills_used.append("us_market_snapshot")

    fallback = _recommend_text(data)
    text = await _polish_with_llm(
        message,
        data,
        fallback,
        history,
        deep_mode=deep_mode,
        model_provider=model_provider,
        system_hint=(
            "这是一个基于今日市场环境的基金推荐请求。"
            "不要说只是基于候选池；要明确说明今日市场证据如何影响筛选。"
            "除非用户明确要求 QDII/海外，不要默认只推荐 QDII，优先给跨类型、可分散的选择。"
            "按 当天/短线/长线 给出是否适合观察、定投、小额加仓或暂缓。"
        ),
    )
    return {
        "text": text,
        "cards": [
            {"type": "recommendations", "title": "市场驱动初筛", "data": data},
            {"type": "market_context", "title": "市场环境", "data": data},
            *([{"type": "portfolio_context", "title": "我的持仓", "data": data["portfolio_context"]}] if data.get("portfolio_context") else []),
            {"type": "rag_context", "title": "知识库引用", "data": {"items": data["rag_context"]}},
        ],
        "skills_used": skills_used,
    }


def _rank_text(data: dict[str, Any]) -> str:
    funds = data.get("funds", [])
    lines = [f"{data.get('fund_type', '基金')}排名前 {len(funds)} 条已取回。"]
    for fund in funds[:8]:
        lines.append(
            f"- {fund.get('name')}（{fund.get('code')}）：近1年 {_format_pct(fund.get('year_return'))}，"
            f"近3月 {_format_pct(fund.get('three_month_return'))}。"
        )
    if data.get("warning"):
        lines.append(data["warning"])
    return "\n".join(lines)


def _compare_text(data: dict[str, Any]) -> str:
    funds = data.get("funds", [])
    lines = ["已完成基金对比，优先看三个维度：近阶段收益、最大回撤、年化波动。"]
    for fund in funds:
        metrics = fund.get("metrics", {})
        lines.append(
            f"- {fund.get('name')}（{fund.get('code')}）：近3月 {_format_pct(metrics.get('three_month_return'))}，"
            f"最大回撤 {_format_pct(metrics.get('max_drawdown'))}，波动 {_format_pct(metrics.get('volatility'))}。"
        )
    return "\n".join(lines)


def _holding_text(data: dict[str, Any]) -> str:
    holdings = data.get("holdings", [])
    if not holdings:
        return data.get("warning") or "没有取得这只基金的持仓披露。"
    top = holdings[:10]
    lines = [f"取得 {data.get('year')} 年持仓 {len(holdings)} 条，前十大持仓如下："]
    for item in top:
        lines.append(
            f"- {item.get('stock_name')}（{item.get('stock_code')}）：占净值 {_format_pct(item.get('hold_ratio'))}"
        )
    lines.append("持仓只能代表最近披露期，和当前实时仓位可能有差异。")
    return "\n".join(lines)


def _detail_text(data: dict[str, Any]) -> str:
    metrics = data.get("metrics", {})
    lines = [
        f"{data.get('name', data.get('code'))}（{data.get('code')}）的最新净值为 {metrics.get('latest_nav') or data.get('latest_nav') or '暂无'}。",
        f"近1月 {_format_pct(metrics.get('month_return'))}，近3月 {_format_pct(metrics.get('three_month_return'))}，"
        f"最大回撤 {_format_pct(metrics.get('max_drawdown'))}，年化波动 {_format_pct(metrics.get('volatility'))}。",
    ]
    # 技术指标
    tech = data.get("technical", {})
    if tech.get("available"):
        rsi_val = tech.get("rsi_14")
        if rsi_val is not None:
            lines.append(f"RSI(14)：{rsi_val:.1f} — {tech.get('rsi_signal', '')}")
        macd_sig = tech.get("macd_signal")
        if macd_sig:
            lines.append(f"MACD：{macd_sig}")
        bb_sig = tech.get("bollinger_signal")
        if bb_sig:
            lines.append(f"布林带：{bb_sig}")
        summary = tech.get("summary")
        if summary:
            lines.append(f"\n综合技术面：{summary}")
    if data.get("warning"):
        lines.append(data["warning"])
    return "\n".join(lines)


def _market_analysis_text(data: dict[str, Any]) -> str:
    fund = data.get("fund_detail") or {}
    sector_context = data.get("sector_context") or {}
    sectors = sector_context.get("selected") or []
    fund_name = fund.get("name") or fund.get("code")
    news_count = len((data.get("market_news") or {}).get("news", []))
    us_count = len((data.get("us_market") or {}).get("items", []))
    evidence = [f"市场快讯 {news_count} 条"]
    if fund:
        evidence.append("基金详情和持仓披露")
    if sectors:
        evidence.append(f"板块实时数据 {len(sectors)} 个")
    if us_count:
        evidence.append(f"美股快照 {us_count} 条")
    lines = [
        f"我按“当天、短线、长线”三层框架看 {fund_name or '目标板块/市场'}。",
        f"已纳入{'、'.join(evidence)}作为证据源。",
    ]
    if sectors:
        lines.extend(["", "板块即时判断："])
        for sector in sectors[:6]:
            label = sector.get("matched_label") or sector.get("name")
            action = "短线可观察，但只适合分批和小仓位" if sector.get("recommend_label") == "优先观察" else (
                "只做跟踪，等待资金和价格共振" if sector.get("recommend_label") == "谨慎跟踪" else "暂缓追高或补仓"
            )
            lines.append(
                f"{label}：对应板块 {sector.get('name')}，涨跌幅 {_format_pct(sector.get('change_pct'))}，"
                f"资金净流 {_format_pct(sector.get('net_inflow')) if sector.get('net_inflow') is None else str(round(float(sector.get('net_inflow')), 2)) + ' 亿'}，"
                f"风险 {sector.get('risk_level')}，结论是{action}。"
            )
    # 技术指标摘要
    tech = fund.get("technical", {})
    if tech.get("available"):
        tech_summary = tech.get("summary", "")
        rsi_val = tech.get("rsi_14")
        macd_sig = tech.get("macd_signal", "")
        lines.append(f"技术面：RSI(14)={rsi_val or '暂无'}，{macd_sig}。{tech_summary}")
    lines.extend(["",
        "当天：只做风险确认，不把单条快讯当作买卖依据。若出现政策/行业突发利好，可观察成交和净值估算是否同步；若利空集中，先避免追涨补仓。",
        "短线：重点看主题热度、重仓行业是否共振、海外市场是否影响 QDII 溢价和情绪。若涨幅已连续兑现，优先分批而不是一次性加仓。",
        "长线：回到基金经理/指数逻辑、行业景气度、估值位置、费率和组合相关性。长期能否持有，取决于它在你组合里是核心仓还是卫星仓。",
        "",
        "操作框架：加仓需要同时满足仓位未超限、风险偏好允许、利好不是一次性事件；减仓通常在单只仓位过高、主题仓过热或基本面逻辑变坏时触发；定投适合逻辑未坏但波动大的基金；转换适合从高相关主题切到低相关资产。",
    ])
    return "\n".join(lines)


async def handle_message(
    message: str,
    history: list[dict[str, Any]] | None = None,
    deep_mode: bool = False,
    model_provider: str | None = None,
) -> dict[str, Any]:
    codes = _extract_codes(message)
    msg = message.strip()
    cards: list[dict[str, Any]] = []
    skills_used: list[str] = []
    rag_context = await _retrieve_rag_context(msg) if msg else []
    portfolio_context = await _build_portfolio_context() if msg and _should_attach_portfolio_context(msg) else None

    if _wants_recommendation(msg) and _is_market_based_request(msg):
        return await _market_based_recommendation(
            msg,
            _detect_top_n(msg),
            history,
            deep_mode=deep_mode,
            model_provider=model_provider,
        )

    if _is_market_analysis_intent(msg) and ("推荐" not in msg or codes):
        data: dict[str, Any] = {}
        if codes:
            detail_skill = skill_registry.get("fund_detail")
            detail_result = await detail_skill.run(code=codes[0])
            data["fund_detail"] = detail_result.data or {}
            skills_used.append(detail_skill.name)

            holding_skill = skill_registry.get("fund_holding")
            holding_result = await holding_skill.run(code=codes[0])
            data["fund_holdings"] = holding_result.data or {}
            skills_used.append(holding_skill.name)
            cards.append({"type": "fund_detail", "title": "基金详情", "data": data["fund_detail"]})
            cards.append({"type": "holdings", "title": "持仓穿透", "data": data["fund_holdings"]})

        news_skill = skill_registry.get("news_fetch")
        news_result = await news_skill.run(limit=20)
        data["market_news"] = news_result.data or {}
        skills_used.append(news_skill.name)

        if any(word in msg.upper() for word in ["QDII", "美股", "纳指", "纳斯达克", "标普", "海外"]):
            data["us_market"] = await get_us_market_snapshot(limit=12)
            skills_used.append("us_market_snapshot")

        if _is_sector_analysis_intent(msg):
            data["sector_context"] = await _build_sector_context(msg)
            skills_used.append("sector_overview")
            cards.append({"type": "sector_context", "title": "板块风向", "data": data["sector_context"]})

        if portfolio_context:
            data["portfolio_context"] = portfolio_context
            cards.append({"type": "portfolio_context", "title": "我的持仓", "data": portfolio_context})

        data["analysis_horizons"] = ["当天", "短线", "长线"]
        data["rag_context"] = rag_context
        cards.append({"type": "market_context", "title": "市场环境", "data": data})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _market_analysis_text(data)
        text = await _polish_with_llm(
            msg,
            data,
            fallback,
            history,
            deep_mode=deep_mode,
            model_provider=model_provider,
            system_hint=(
                "请按 当天/短线/长线 三段给出操作框架。"
                "必须覆盖利好、利空、大趋势、政策、供需、海外/美股影响中与问题相关的部分。"
                "如果用户问板块或行业，必须逐一引用 sector_context.selected 中的板块涨跌、资金净流、风险等级和推荐标签。"
                "对每个板块都要明确回答：短线能否继续操作、适合观察/小仓位/暂缓/减仓中的哪一种。"
                "输出要能指导定投、加仓、减仓、转换、观望，但不要承诺收益。"
            ),
        )
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if _wants_recommendation(msg):
        skill = skill_registry.get("fund_recommend")
        result = await skill.run(
            fund_type=_detect_fund_type(msg),
            risk_preference=_detect_risk(msg),
            top_n=_detect_top_n(msg),
        )
        data = result.data or {}
        data["rag_context"] = rag_context
        if portfolio_context:
            data["portfolio_context"] = portfolio_context
        skills_used.append(skill.name)
        cards.append({"type": "recommendations", "title": "基金候选", "data": data})
        if portfolio_context:
            cards.append({"type": "portfolio_context", "title": "我的持仓", "data": portfolio_context})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _recommend_text(data)
        text = await _polish_with_llm(msg, data, fallback, history, deep_mode=deep_mode, model_provider=model_provider)
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if portfolio_context:
        data = {"portfolio_context": portfolio_context, "rag_context": rag_context}
        cards.append({"type": "portfolio_context", "title": "我的持仓", "data": portfolio_context})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _portfolio_text(portfolio_context)
        text = await _polish_with_llm(
            msg,
            data,
            fallback,
            history,
            deep_mode=deep_mode,
            model_provider=model_provider,
            system_hint=(
                "这是用户个人组合问题。必须引用 portfolio_context 中的持仓市值、盈亏/快照日盈亏、净值涨跌/快照涨跌、QDII/主题仓位和前几大持仓；不要把导入快照说成今天实时数据。"
                "回答要说明这些数据来自用户已导入持仓和最新净值估算，不要假装已经知道券商/支付宝实时账户。"
            ),
        )
        return {"text": text, "cards": cards, "skills_used": ["portfolio_context"]}

    if "对比" in msg or "比较" in msg:
        if len(codes) < 2:
            text = "请给我 2-5 个 6 位基金代码，我可以对比净值、回撤和波动。"
            return {"text": text, "cards": cards, "skills_used": skills_used}
        skill = skill_registry.get("fund_compare")
        result = await skill.run(codes=codes[:5])
        data = result.data or {}
        data["rag_context"] = rag_context
        skills_used.append(skill.name)
        cards.append({"type": "comparison", "title": "基金对比", "data": data})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _compare_text(data)
        text = await _polish_with_llm(msg, data, fallback, history, deep_mode=deep_mode, model_provider=model_provider)
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if "持仓" in msg and codes:
        skill = skill_registry.get("fund_holding")
        result = await skill.run(code=codes[0])
        data = result.data or {}
        data["rag_context"] = rag_context
        skills_used.append(skill.name)
        cards.append({"type": "holdings", "title": "持仓穿透", "data": data})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _holding_text(data)
        text = await _polish_with_llm(msg, data, fallback, history, deep_mode=deep_mode, model_provider=model_provider)
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if "排名" in msg or "排行" in msg:
        skill = skill_registry.get("fund_rank")
        result = await skill.run(fund_type=_detect_fund_type(msg), top_n=20)
        data = result.data or {}
        data["rag_context"] = rag_context
        skills_used.append(skill.name)
        cards.append({"type": "rank", "title": "基金雷达", "data": data})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _rank_text(data)
        text = await _polish_with_llm(msg, data, fallback, history, deep_mode=deep_mode, model_provider=model_provider)
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if ("新闻" in msg or "快讯" in msg) and codes:
        skill = skill_registry.get("news_fetch")
        result = await skill.run(code=codes[0], limit=10)
        data = result.data or {}
        skills_used.append(skill.name)
        cards.append({"type": "news", "title": "新闻", "data": data})
        text = f"已取回 {codes[0]} 的新闻条目 {len(data.get('news', []))} 条。新闻只作为辅助证据，不能单独触发买卖。"
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if ("股票" in msg or "行情" in msg or "个股" in msg) and codes:
        skill = skill_registry.get("stock_quote")
        result = await skill.run(code=codes[0])
        data = result.data or {"error": result.error}
        skills_used.append(skill.name)
        cards.append({"type": "stock_quote", "title": "股票行情", "data": data})
        text = f"已查询 {codes[0]} 行情。股票数据在本项目里主要用于基金持仓穿透和风险归因。"
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if codes:
        skill = skill_registry.get("fund_detail")
        result = await skill.run(code=codes[0])
        data = result.data or {}
        data["rag_context"] = rag_context
        skills_used.append(skill.name)
        cards.append({"type": "fund_detail", "title": "基金详情", "data": data})
        if rag_context:
            cards.append({"type": "rag_context", "title": "知识库引用", "data": {"items": rag_context}})
        fallback = _detail_text(data)
        text = await _polish_with_llm(msg, data, fallback, history, deep_mode=deep_mode, model_provider=model_provider)
        return {"text": text, "cards": cards, "skills_used": skills_used}

    if msg:
        skill = skill_registry.get("fund_search")
        result = await skill.run(query=msg, limit=10)
        data = result.data or {}
        skills_used.append(skill.name)
        cards.append({"type": "search", "title": "基金搜索", "data": data})
        funds = data.get("funds", [])
        if funds:
            text = "我先按关键词找到了这些基金，你可以继续让我对比、看持仓或生成候选建议。"
        else:
            text = "我还没有定位到具体基金。你可以输入基金代码，或问“推荐几只 QDII 基金”。"
        return {"text": text, "cards": cards, "skills_used": skills_used}

    return {
        "text": "你可以问我：推荐几只 QDII 基金、对比 040046 和 270042、查看 110020 持仓。",
        "cards": cards,
        "skills_used": skills_used,
    }
