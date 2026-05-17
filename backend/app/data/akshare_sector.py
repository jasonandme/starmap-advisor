"""行业板块数据聚合。

用 AKShare 的东方财富行业板块和行业资金流数据做第一版板块雷达：
涨跌、资金净流、风险分层、推荐评分和相关新闻线索都在这里统一归一化。
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
from datetime import datetime
from typing import Any

import akshare as ak
import pandas as pd

from app.config import get_settings
from app.data.akshare_fund import clean_value
from app.data.akshare_news import get_market_flash
from app.data.cache import cache


settings = get_settings()


def _num(value: Any) -> float | None:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    for unit in ("亿元", "亿", "万元", "万", "元"):
        text = text.replace(unit, "")
    if text in {"", "-", "--", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _text(value: Any, default: str = "") -> str:
    value = clean_value(value)
    if value is None:
        return default
    return str(value).strip()


def _risk_level(score: float) -> str:
    if score >= 70:
        return "高"
    if score >= 45:
        return "中"
    return "低"


def _normalize_name(name: str) -> str:
    return name.replace("行业", "").replace("板块", "").strip()


def _risk_score(row: dict[str, Any]) -> float:
    change_pct = abs(row.get("change_pct") or 0)
    turnover = row.get("turnover_rate") or 0
    rising = row.get("rising_count") or 0
    falling = row.get("falling_count") or 0
    total = max(rising + falling, 1)
    falling_ratio = falling / total
    net_inflow = row.get("net_inflow")

    score = 18
    score += min(change_pct * 9, 34)
    score += min(turnover * 4, 22)
    score += max(falling_ratio - 0.45, 0) * 38
    if net_inflow is not None and net_inflow < 0:
        score += min(abs(net_inflow) * 0.45, 18)
    return round(min(score, 100), 2)


def _recommend_score(row: dict[str, Any]) -> float:
    change_pct = row.get("change_pct") or 0
    net_inflow = row.get("net_inflow") or 0
    turnover = row.get("turnover_rate") or 0
    rising = row.get("rising_count") or 0
    falling = row.get("falling_count") or 0
    total = rising + falling
    rising_ratio = rising / total if total > 0 else None
    risk = row.get("risk_score") or 50

    flow_score = math.tanh(net_inflow / 35) * 35
    momentum_score = max(min(change_pct * 7, 28), -24)
    breadth_score = (rising_ratio - 0.5) * 28 if rising_ratio is not None else 0
    turnover_score = 8 if 1.2 <= turnover <= 6.5 else (0 if turnover == 0 else -4)
    risk_penalty = max(risk - 62, 0) * 0.55
    return round(50 + flow_score + momentum_score + breadth_score + turnover_score - risk_penalty, 2)


def _reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    net = row.get("net_inflow")
    change = row.get("change_pct")
    risk = row.get("risk_level")
    if net is not None:
        if net > 0:
            reasons.append(f"资金净流入约 {net:.2f} 亿，短线关注度较高")
        elif net < 0:
            reasons.append(f"资金净流出约 {abs(net):.2f} 亿，需要观察承接")
    if change is not None:
        reasons.append(f"板块涨跌幅 {change:.2f}%，反映当日强弱")
    if row.get("leading_stock"):
        reasons.append(f"领涨股为 {row['leading_stock']}")
    reasons.append(f"风险分层为{risk}，适合作为仓位和节奏约束")
    return reasons[:4]


def _normalize_sector_rows(board_df: pd.DataFrame, flow_df: pd.DataFrame) -> list[dict[str, Any]]:
    flow_by_name: dict[str, dict[str, Any]] = {}
    for _, record in flow_df.iterrows():
        item = record.to_dict()
        name = _text(item.get("行业"))
        if name:
            flow_by_name[_normalize_name(name)] = item

    rows: list[dict[str, Any]] = []
    for _, record in board_df.iterrows():
        raw = record.to_dict()
        name = _text(raw.get("板块名称"))
        if not name:
            continue
        flow = flow_by_name.get(_normalize_name(name), {})
        row = {
            "name": name,
            "code": _text(raw.get("板块代码")),
            "latest_price": _num(raw.get("最新价")),
            "change_amount": _num(raw.get("涨跌额")),
            "change_pct": _num(raw.get("涨跌幅")),
            "market_value": _num(raw.get("总市值")),
            "turnover_rate": _num(raw.get("换手率")),
            "rising_count": int(_num(raw.get("上涨家数")) or 0),
            "falling_count": int(_num(raw.get("下跌家数")) or 0),
            "leading_stock": _text(raw.get("领涨股票") or flow.get("领涨股")),
            "leading_stock_change_pct": _num(raw.get("领涨股票-涨跌幅") or flow.get("领涨股-涨跌幅")),
            "inflow": _num(flow.get("流入资金")),
            "outflow": _num(flow.get("流出资金")),
            "net_inflow": _num(flow.get("净额")),
            "company_count": int(_num(flow.get("公司家数")) or 0),
            "source": "AKShare / 东方财富",
        }
        row["risk_score"] = _risk_score(row)
        row["risk_level"] = _risk_level(row["risk_score"])
        row["recommend_score"] = _recommend_score(row)
        row["recommend_label"] = "优先观察" if row["recommend_score"] >= 62 and row["risk_level"] != "高" else (
            "谨慎跟踪" if row["recommend_score"] >= 48 else "暂缓"
        )
        row["reasons"] = _reasons(row)
        rows.append(row)
    return rows


def _normalize_flow_rows(flow_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, record in flow_df.iterrows():
        raw = record.to_dict()
        name = _text(raw.get("行业"))
        if not name:
            continue
        row = {
            "name": name,
            "code": "",
            "latest_price": _num(raw.get("行业指数")),
            "change_amount": None,
            "change_pct": _num(raw.get("行业-涨跌幅")),
            "market_value": None,
            "turnover_rate": None,
            "rising_count": 0,
            "falling_count": 0,
            "leading_stock": _text(raw.get("领涨股")),
            "leading_stock_change_pct": _num(raw.get("领涨股-涨跌幅")),
            "inflow": _num(raw.get("流入资金")),
            "outflow": _num(raw.get("流出资金")),
            "net_inflow": _num(raw.get("净额")),
            "company_count": int(_num(raw.get("公司家数")) or 0),
            "source": "AKShare / 东方财富资金流",
        }
        row["risk_score"] = _risk_score(row)
        row["risk_level"] = _risk_level(row["risk_score"])
        row["recommend_score"] = _recommend_score(row)
        row["recommend_label"] = "优先观察" if row["recommend_score"] >= 62 and row["risk_level"] != "高" else (
            "谨慎跟踪" if row["recommend_score"] >= 48 else "暂缓"
        )
        row["reasons"] = _reasons(row)
        rows.append(row)
    return rows


def _normalize_ths_rows(ths_df: pd.DataFrame, flow_df: pd.DataFrame) -> list[dict[str, Any]]:
    flow_by_name: dict[str, dict[str, Any]] = {}
    for _, record in flow_df.iterrows():
        item = record.to_dict()
        name = _text(item.get("行业"))
        if name:
            flow_by_name[_normalize_name(name)] = item

    rows: list[dict[str, Any]] = []
    for _, record in ths_df.iterrows():
        raw = record.to_dict()
        name = _text(raw.get("板块"))
        if not name:
            continue
        flow = flow_by_name.get(_normalize_name(name), {})
        row = {
            "name": name,
            "code": "",
            "latest_price": _num(flow.get("行业指数") or raw.get("均价")),
            "change_amount": None,
            "change_pct": _num(raw.get("涨跌幅") or flow.get("行业-涨跌幅")),
            "market_value": None,
            "turnover_rate": None,
            "rising_count": int(_num(raw.get("上涨家数")) or 0),
            "falling_count": int(_num(raw.get("下跌家数")) or 0),
            "leading_stock": _text(raw.get("领涨股") or flow.get("领涨股")),
            "leading_stock_change_pct": _num(raw.get("领涨股-涨跌幅") or flow.get("领涨股-涨跌幅")),
            "inflow": _num(flow.get("流入资金")),
            "outflow": _num(flow.get("流出资金")),
            "net_inflow": _num(raw.get("净流入") or flow.get("净额")),
            "company_count": int((_num(raw.get("上涨家数")) or 0) + (_num(raw.get("下跌家数")) or 0)),
            "amount": _num(raw.get("总成交额")),
            "volume": _num(raw.get("总成交量")),
            "source": "AKShare / 同花顺行业汇总",
        }
        row["risk_score"] = _risk_score(row)
        row["risk_level"] = _risk_level(row["risk_score"])
        row["recommend_score"] = _recommend_score(row)
        row["recommend_label"] = "优先观察" if row["recommend_score"] >= 62 and row["risk_level"] != "高" else (
            "谨慎跟踪" if row["recommend_score"] >= 48 else "暂缓"
        )
        row["reasons"] = _reasons(row)
        rows.append(row)
    return rows


async def get_sector_overview(limit: int = 80) -> dict[str, Any]:
    key = f"sector:overview:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    # 同花顺行业汇总内部依赖 py_mini_racer/V8；Windows 下可能触发原生 fatal crash，
    # 这类崩溃无法被 try/except 捕获，会直接杀掉 FastAPI 进程。默认禁用，仅在显式开关下启用。
    board_result = await asyncio.gather(
        asyncio.to_thread(ak.stock_board_industry_name_em),
        return_exceptions=True,
    )
    board_result = board_result[0]
    allow_ths = os.getenv("STARMAP_ENABLE_THS_SECTOR", "").lower() in {"1", "true", "yes"}
    if allow_ths or not sys.platform.startswith("win"):
        try:
            ths_result = await asyncio.to_thread(ak.stock_board_industry_summary_ths)
        except Exception as exc:
            ths_result = exc
    else:
        ths_result = RuntimeError("Windows 环境默认禁用同花顺行业汇总，避免 py_mini_racer 原生崩溃。")
    flow_result = await asyncio.gather(
        asyncio.to_thread(ak.stock_fund_flow_industry),
        return_exceptions=True,
    )
    flow_result = flow_result[0]
    warnings: list[str] = []
    board_df = pd.DataFrame() if isinstance(board_result, Exception) else board_result
    ths_df = pd.DataFrame() if isinstance(ths_result, Exception) else ths_result
    flow_df = pd.DataFrame() if isinstance(flow_result, Exception) else flow_result
    if isinstance(board_result, Exception) and isinstance(ths_result, Exception):
        warnings.append("东方财富行业全量行情和同花顺行业汇总均暂不可用，已使用行业资金流接口继续分析。")
    if isinstance(flow_result, Exception):
        warnings.append("行业资金流接口暂不可用，资金流字段会缺失。")
    if (board_df is None or board_df.empty) and (ths_df is None or ths_df.empty) and (flow_df is None or flow_df.empty):
        error = board_result if isinstance(board_result, Exception) else (ths_result if isinstance(ths_result, Exception) else flow_result)
        raise RuntimeError(f"未取得行业板块数据：{error}")

    if board_df is not None and not board_df.empty:
        sectors = _normalize_sector_rows(board_df, flow_df if flow_df is not None else pd.DataFrame())
        quote_source = "eastmoney"
    elif ths_df is not None and not ths_df.empty:
        sectors = _normalize_ths_rows(ths_df, flow_df if flow_df is not None else pd.DataFrame())
        quote_source = "ths"
    else:
        sectors = _normalize_flow_rows(flow_df)
        quote_source = "fund_flow"
    sectors.sort(key=lambda item: item.get("recommend_score", 0), reverse=True)
    selected = sectors[:limit]
    recommended = [item for item in sectors if item["recommend_label"] == "优先观察"][:8]
    risk_alerts = sorted(sectors, key=lambda item: item["risk_score"], reverse=True)[:8]

    flow_items = [item for item in sectors if item.get("net_inflow") is not None]
    total_net = round(sum(item.get("net_inflow") or 0 for item in flow_items), 2)
    total_in = round(sum(item.get("inflow") or 0 for item in flow_items), 2)
    total_out = round(sum(item.get("outflow") or 0 for item in flow_items), 2)
    result = {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(selected),
        "sectors": selected,
        "recommended": recommended,
        "risk_alerts": risk_alerts,
        "flow_summary": {
            "total_inflow": total_in,
            "total_outflow": total_out,
            "total_net_inflow": total_net,
            "positive_count": sum(1 for item in flow_items if (item.get("net_inflow") or 0) > 0),
            "negative_count": sum(1 for item in flow_items if (item.get("net_inflow") or 0) < 0),
        },
        "source": "AKShare / 东方财富",
        "data_quality": {
            "industry_quote_status": "ok" if quote_source in {"eastmoney", "ths"} else "partial",
            "industry_quote_source": quote_source,
            "industry_flow_status": "fail" if isinstance(flow_result, Exception) else "ok",
            "industry_quote_error": str(board_result)[:500] if isinstance(board_result, Exception) else None,
            "note": "东方财富行业全量行情不可用时，会自动切到同花顺行业汇总；若两者都不可用，才使用行业资金流兜底。",
        },
    }
    if warnings:
        result["warnings"] = warnings
    cache.set(key, result, settings.CACHE_QUOTE_TTL)
    return result


async def get_sector_news(name: str, limit: int = 10) -> dict[str, Any]:
    flash = await get_market_flash(limit=80)
    news = flash.get("news", [])
    keyword = _normalize_name(name)
    matched: list[dict[str, Any]] = []
    clean_news: list[dict[str, Any]] = []
    for item in news:
        text = " ".join(str(value) for value in item.values() if value is not None)
        if _looks_garbled(text):
            continue
        clean_news.append(item)
        if keyword and keyword in text:
            matched.append(item)
    fallback_news: list[dict[str, Any]] = []
    if not matched and not clean_news:
        try:
            overview = await get_sector_overview(limit=120)
            sectors = overview.get("sectors", [])
            sector = next((row for row in sectors if _normalize_name(row.get("name", "")) == keyword), None)
            if sector:
                fallback_news = _build_sector_signal_news(sector)
        except Exception:
            fallback_news = []
    return {
        "name": name,
        "news": matched[:limit] if matched else clean_news[:limit] if clean_news else fallback_news[:limit],
        "matched": bool(matched),
        "source": flash.get("source", "AKShare") if clean_news or matched else "sector_market_signal",
        "warning": flash.get("warning")
        or (None if matched else "暂无完全匹配的板块资讯，先展示市场快讯作为背景。")
        if clean_news
        else "实时快讯源暂未返回可展示内容，已用板块行情和资金流生成资讯摘要。",
    }


def _build_sector_signal_news(sector: dict[str, Any]) -> list[dict[str, Any]]:
    name = sector.get("name") or "该板块"
    change_pct = sector.get("change_pct")
    net_inflow = sector.get("net_inflow")
    leading_stock = sector.get("leading_stock") or "暂无"
    risk_level = sector.get("risk_level") or "待确认"
    recommend_label = sector.get("recommend_label") or "观察"
    reasons = sector.get("reasons") or []
    summary_parts = [
        f"{name}板块当前涨跌幅 {change_pct:.2f}%" if isinstance(change_pct, (int, float)) else f"{name}板块当前涨跌幅暂无",
        f"资金净流 {'流入' if isinstance(net_inflow, (int, float)) and net_inflow >= 0 else '流出'} {abs(net_inflow):.2f} 亿元"
        if isinstance(net_inflow, (int, float))
        else "资金净流暂无",
        f"领涨股为 {leading_stock}",
        f"风险分层为{risk_level}，系统建议：{recommend_label}",
    ]
    items = [
        {
            "time": overview_time_now(),
            "summary": "；".join(summary_parts) + "。",
            "source": "板块行情摘要",
        }
    ]
    for reason in reasons[:3]:
        items.append(
            {
                "time": overview_time_now(),
                "summary": str(reason),
                "source": "板块判断依据",
            }
        )
    return items


def overview_time_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _looks_garbled(text: str) -> bool:
    bad_tokens = ["�", "ï¿½", "����", "\ufffd"]
    bad_count = sum(text.count(token) for token in bad_tokens)
    return bad_count >= 2 or bad_count / max(len(text), 1) > 0.05
