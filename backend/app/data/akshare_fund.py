"""
AKShare 基金数据接入与指标清洗。

原则：
1. AKShare/东方财富等结构化接口负责拿数据。
2. 本层负责字段归一化、缓存、失败降级和基础指标计算。
3. LLM 只消费这里返回的结构化对象，不直接解析网页。
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from app.config import get_settings
from app.data.cache import cache
from app.data.technical import compute_technical_indicators


settings = get_settings()


SUPPORTED_FUND_TYPES = ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF", "LOF"]


FALLBACK_FUNDS: list[dict[str, Any]] = [
    {
        "code": "110020",
        "name": "易方达沪深300ETF联接A",
        "fund_type": "指数型",
        "unit_nav": 1.511,
        "daily_return": 0.18,
        "month_return": 2.8,
        "three_month_return": 8.4,
        "six_month_return": 12.6,
        "year_return": 15.2,
        "this_year_return": 7.9,
        "source": "demo_fallback",
    },
    {
        "code": "000311",
        "name": "景顺长城沪深300增强A",
        "fund_type": "指数型",
        "unit_nav": 2.431,
        "daily_return": 0.11,
        "month_return": 2.1,
        "three_month_return": 7.2,
        "six_month_return": 13.1,
        "year_return": 16.8,
        "this_year_return": 8.1,
        "source": "demo_fallback",
    },
    {
        "code": "161725",
        "name": "招商中证白酒指数A",
        "fund_type": "指数型",
        "unit_nav": 0.842,
        "daily_return": -0.42,
        "month_return": -1.6,
        "three_month_return": 4.2,
        "six_month_return": 7.5,
        "year_return": 5.3,
        "this_year_return": 2.4,
        "source": "demo_fallback",
    },
    {
        "code": "040046",
        "name": "华安纳斯达克100ETF联接A(QDII)",
        "fund_type": "QDII",
        "unit_nav": 5.214,
        "daily_return": 0.36,
        "month_return": 4.6,
        "three_month_return": 9.1,
        "six_month_return": 18.2,
        "year_return": 31.5,
        "this_year_return": 14.0,
        "source": "demo_fallback",
    },
    {
        "code": "270042",
        "name": "广发纳斯达克100ETF联接A(QDII)",
        "fund_type": "QDII",
        "unit_nav": 4.982,
        "daily_return": 0.29,
        "month_return": 4.1,
        "three_month_return": 8.7,
        "six_month_return": 17.4,
        "year_return": 29.6,
        "this_year_return": 13.5,
        "source": "demo_fallback",
    },
    {
        "code": "050025",
        "name": "博时标普500ETF联接A(QDII)",
        "fund_type": "QDII",
        "unit_nav": 3.114,
        "daily_return": 0.18,
        "month_return": 3.0,
        "three_month_return": 6.2,
        "six_month_return": 12.8,
        "year_return": 22.4,
        "this_year_return": 9.8,
        "source": "demo_fallback",
    },
    {
        "code": "000191",
        "name": "富国信用债债券A",
        "fund_type": "债券型",
        "unit_nav": 1.093,
        "daily_return": 0.02,
        "month_return": 0.4,
        "three_month_return": 1.1,
        "six_month_return": 2.3,
        "year_return": 4.5,
        "this_year_return": 1.7,
        "source": "demo_fallback",
    },
]


def _is_missing(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return value is None


def clean_value(value: Any) -> Any:
    if _is_missing(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, str):
        text = value.strip()
        if text in {"", "--", "-", "nan", "None"}:
            return None
        return text
    return value


def to_float(value: Any) -> float | None:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    text = text.replace("亿元", "").replace("亿", "").replace("万", "")
    if text in {"", "--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick(row: dict[str, Any], names: list[str], default: Any = None) -> Any:
    for name in names:
        if name in row:
            value = clean_value(row[name])
            if value is not None:
                return value
    return default


def normalize_fund_type(fund_type: str | None) -> str:
    if not fund_type:
        return "全部"
    text = fund_type.strip().upper()
    mapping = {
        "ALL": "全部",
        "全部基金": "全部",
        "STOCK": "股票型",
        "股票": "股票型",
        "混合": "混合型",
        "BOND": "债券型",
        "债券": "债券型",
        "INDEX": "指数型",
        "指数": "指数型",
        "QDII": "QDII",
    }
    return mapping.get(text, fund_type.strip())


def _normalize_rank_record(row: dict[str, Any], fund_type: str) -> dict[str, Any]:
    record = {
        "code": str(pick(row, ["基金代码", "代码", "fund_code"], "")),
        "name": str(pick(row, ["基金简称", "基金名称", "简称", "name"], "")),
        "fund_type": pick(row, ["基金类型", "类型"], fund_type),
        "nav_date": pick(row, ["日期", "净值日期", "nav_date"]),
        "unit_nav": to_float(pick(row, ["单位净值", "最新净值", "净值"])),
        "acc_nav": to_float(pick(row, ["累计净值"])),
        "daily_return": to_float(pick(row, ["日增长率", "日涨幅", "涨跌幅"])),
        "week_return": to_float(pick(row, ["近1周", "近一周"])),
        "month_return": to_float(pick(row, ["近1月", "近一月"])),
        "three_month_return": to_float(pick(row, ["近3月", "近三月"])),
        "six_month_return": to_float(pick(row, ["近6月", "近六月"])),
        "year_return": to_float(pick(row, ["近1年", "近一年"])),
        "two_year_return": to_float(pick(row, ["近2年", "近二年"])),
        "three_year_return": to_float(pick(row, ["近3年", "近三年"])),
        "this_year_return": to_float(pick(row, ["今年来", "今年以来"])),
        "since_inception_return": to_float(pick(row, ["成立来", "成立以来"])),
        "fee": pick(row, ["手续费", "申购费率", "费率"]),
        "source": "akshare",
        "raw": {key: clean_value(value) for key, value in row.items()},
    }
    return record


def _fallback_rank(fund_type: str, top_n: int) -> dict[str, Any]:
    fund_type = normalize_fund_type(fund_type)
    items = [
        item for item in FALLBACK_FUNDS
        if fund_type == "全部" or item["fund_type"] == fund_type
    ]
    return {
        "fund_type": fund_type,
        "count": len(items[:top_n]),
        "funds": items[:top_n],
        "source": "demo_fallback",
        "as_of": "演示数据，AKShare 不可用时用于本地界面降级",
        "warning": "当前为演示降级数据，请勿据此交易。",
    }


def _fallback_search(query: str) -> dict[str, Any]:
    q = query.lower()
    items = [
        {
            "code": item["code"],
            "name": item["name"],
            "fund_type": item["fund_type"],
            "source": item["source"],
        }
        for item in FALLBACK_FUNDS
        if q in item["code"].lower() or q in item["name"].lower() or q in item["fund_type"].lower()
    ]
    return {
        "count": len(items),
        "funds": items,
        "source": "demo_fallback",
        "warning": "当前为演示降级数据，请勿据此交易。",
    }


async def search_funds(query: str, limit: int = 20, force_refresh: bool = False) -> dict[str, Any]:
    key = f"fund:search:{query}:{limit}"
    cached = None if force_refresh else cache.get(key)
    if cached is not None:
        return cached

    try:
        df = await asyncio.to_thread(ak.fund_name_em)
        if df is None or df.empty:
            raise RuntimeError("AKShare fund_name_em 返回空数据")
        q = query.lower().strip()
        rows: list[dict[str, Any]] = []
        for _, record in df.iterrows():
            row = record.to_dict()
            code = str(pick(row, ["基金代码", "代码"], ""))
            name = str(pick(row, ["基金简称", "基金名称", "简称"], ""))
            fund_type = str(pick(row, ["基金类型", "类型"], ""))
            if q in code.lower() or q in name.lower() or q in fund_type.lower():
                rows.append({
                    "code": code,
                    "name": name,
                    "fund_type": fund_type,
                    "source": "akshare",
                })
            if len(rows) >= limit:
                break
        result = {"count": len(rows), "funds": rows, "source": "akshare"}
        cache.set(key, result, settings.CACHE_FUND_LIST_TTL)
        return result
    except Exception as exc:
        result = _fallback_search(query)
        result["error"] = str(exc)
        return result


async def get_fund_rank(fund_type: str = "全部", top_n: int = 20, force_refresh: bool = False) -> dict[str, Any]:
    fund_type = normalize_fund_type(fund_type)
    key = f"fund:rank:{fund_type}:{top_n}"
    cached = None if force_refresh else cache.get(key)
    if cached is not None:
        return cached

    try:
        df = await asyncio.to_thread(ak.fund_open_fund_rank_em, symbol=fund_type)
        if df is None or df.empty:
            raise RuntimeError("AKShare fund_open_fund_rank_em 返回空数据")
        funds = [
            _normalize_rank_record(record.to_dict(), fund_type)
            for _, record in df.head(top_n).iterrows()
        ]
        result = {
            "fund_type": fund_type,
            "count": len(funds),
            "funds": funds,
            "source": "akshare",
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cache.set(key, result, settings.CACHE_RANK_TTL)
        return result
    except Exception as exc:
        result = _fallback_rank(fund_type, top_n)
        result["error"] = str(exc)
        return result


def _build_demo_nav(code: str) -> list[dict[str, Any]]:
    base = next((item["unit_nav"] for item in FALLBACK_FUNDS if item["code"] == code), 1.0)
    today = datetime.now().date()
    points: list[dict[str, Any]] = []
    for index in range(120):
        days_back = 119 - index
        date = today - timedelta(days=days_back)
        drift = 1 + (index - 60) * 0.0015
        wave = 1 + math.sin(index / 9) * 0.015
        nav = max(base * drift * wave, 0.1)
        prev_nav = points[-1]["nav"] if points else nav
        daily_return = (nav / prev_nav - 1) * 100 if prev_nav else 0
        points.append({
            "date": date.strftime("%Y-%m-%d"),
            "nav": round(nav, 4),
            "daily_return": round(daily_return, 4),
        })
    return points


async def get_fund_nav(code: str, limit: int = 180, force_refresh: bool = False) -> dict[str, Any]:
    key = f"fund:nav:{code}:{limit}"
    cached = None if force_refresh else cache.get(key)
    if cached is not None:
        return cached

    try:
        df = await asyncio.to_thread(
            ak.fund_open_fund_info_em,
            symbol=code,
            indicator="单位净值走势",
            period="1年",
        )
        if df is None or df.empty:
            raise RuntimeError("AKShare fund_open_fund_info_em 返回空数据")
        points: list[dict[str, Any]] = []
        for _, record in df.tail(limit).iterrows():
            row = record.to_dict()
            values = list(row.values())
            date_value = pick(row, ["净值日期", "日期"], values[0] if values else None)
            nav_value = pick(row, ["单位净值", "净值"], values[1] if len(values) > 1 else None)
            daily_value = pick(row, ["日增长率", "日涨幅"], values[2] if len(values) > 2 else None)
            points.append({
                "date": str(clean_value(date_value)),
                "nav": to_float(nav_value),
                "daily_return": to_float(daily_value),
            })
        result = {
            "code": code,
            "nav_history": [point for point in points if point["nav"] is not None],
            "source": "akshare",
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cache.set(key, result, settings.CACHE_QUOTE_TTL)
        return result
    except Exception as exc:
        return {
            "code": code,
            "nav_history": _build_demo_nav(code)[-limit:],
            "source": "demo_fallback",
            "warning": "当前为演示降级净值，请勿据此交易。",
            "error": str(exc),
        }


def calculate_nav_metrics(nav_history: list[dict[str, Any]]) -> dict[str, float | None]:
    values = [point["nav"] for point in nav_history if point.get("nav") is not None]
    if len(values) < 2:
        return {
            "latest_nav": values[-1] if values else None,
            "month_return": None,
            "three_month_return": None,
            "six_month_return": None,
            "year_return": None,
            "max_drawdown": None,
            "volatility": None,
        }

    def period_return(days: int) -> float | None:
        if len(values) <= days:
            return None
        base = values[-days - 1]
        if not base:
            return None
        return round((values[-1] / base - 1) * 100, 4)

    peak = values[0]
    max_drawdown = 0.0
    returns: list[float] = []
    for index, value in enumerate(values):
        peak = max(peak, value)
        if peak:
            max_drawdown = min(max_drawdown, value / peak - 1)
        if index > 0 and values[index - 1]:
            returns.append(value / values[index - 1] - 1)
    volatility = None
    if len(returns) > 2:
        series = pd.Series(returns)
        volatility = round(float(series.std() * math.sqrt(252) * 100), 4)
    return {
        "latest_nav": round(values[-1], 4),
        "month_return": period_return(20),
        "three_month_return": period_return(60),
        "six_month_return": period_return(120),
        "year_return": period_return(240),
        "max_drawdown": round(max_drawdown * 100, 4),
        "volatility": volatility,
    }


async def get_fund_detail(code: str, force_refresh: bool = False) -> dict[str, Any]:
    key = f"fund:detail:{code}"
    cached = None if force_refresh else cache.get(key)
    if cached is not None:
        return cached
    nav, search = await asyncio.gather(
        get_fund_nav(code, force_refresh=force_refresh),
        search_funds(code, limit=5, force_refresh=force_refresh),
    )
    matched = next(
        (item for item in search.get("funds", []) if item.get("code") == code),
        None,
    )
    fallback = next((item for item in FALLBACK_FUNDS if item["code"] == code), None)
    metrics = calculate_nav_metrics(nav.get("nav_history", []))
    # 计算技术指标
    tech = compute_technical_indicators(nav.get("nav_history", []))
    result = {
        "code": code,
        "name": (matched or fallback or {}).get("name", code),
        "fund_type": (matched or fallback or {}).get("fund_type"),
        "latest_nav": metrics["latest_nav"],
        "metrics": metrics,
        "technical": tech,
        "nav_history": nav.get("nav_history", []),
        "source": nav.get("source", "akshare"),
        "as_of": nav.get("as_of"),
    }
    if nav.get("warning"):
        result["warning"] = nav["warning"]
    cache.set(key, result, settings.CACHE_RANK_TTL)
    return result


async def get_latest_fund_quote(code: str, force_refresh: bool = False) -> dict[str, Any]:
    """获取单只基金最新净值和最近一日净值涨跌。"""
    nav = await get_fund_nav(code, limit=8, force_refresh=force_refresh)
    history = [point for point in nav.get("nav_history", []) if point.get("nav") is not None]
    latest = history[-1] if history else {}
    previous = history[-2] if len(history) >= 2 else {}
    latest_nav = to_float(latest.get("nav"))
    previous_nav = to_float(previous.get("nav"))
    daily_return = to_float(latest.get("daily_return"))
    if daily_return is None and latest_nav is not None and previous_nav:
        daily_return = round((latest_nav / previous_nav - 1) * 100, 4)
    return {
        "code": code,
        "latest_nav": latest_nav,
        "previous_nav": previous_nav,
        "nav_date": latest.get("date"),
        "daily_return": daily_return,
        "source": nav.get("source", "akshare"),
        "as_of": nav.get("as_of"),
        "warning": nav.get("warning"),
        "error": nav.get("error"),
    }


async def get_fund_quotes_map(codes: list[str], force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Batch fetch fund quote snapshots for portfolio/watchlist tables."""
    unique_codes = sorted({str(code).strip().zfill(6) for code in codes if str(code).strip()})
    if not unique_codes:
        return {}
    cache_key = "fund:quotes:" + ",".join(unique_codes)
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    target = set(unique_codes)
    rows: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    try:
        df = await asyncio.to_thread(ak.fund_open_fund_rank_em, symbol="全部")
        if df is None or df.empty:
            raise RuntimeError("AKShare fund_open_fund_rank_em returned empty data")
        for _, record in df.iterrows():
            normalized = _normalize_rank_record(record.to_dict(), "全部")
            fund_code = str(normalized.get("code") or "").strip().zfill(6)
            if fund_code not in target:
                continue
            rows[fund_code] = {
                "code": fund_code,
                "name": normalized.get("name"),
                "fund_type": normalized.get("fund_type"),
                "latest_nav": normalized.get("unit_nav"),
                "previous_nav": None,
                "nav_date": normalized.get("nav_date"),
                "daily_return": normalized.get("daily_return"),
                "source": "akshare_fund_rank_quote",
                "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    except Exception as exc:
        errors.append(str(exc))

    missing_codes = [code for code in unique_codes if code not in rows]
    if missing_codes:
        semaphore = asyncio.Semaphore(8)

        async def load_one(fund_code: str) -> tuple[str, dict[str, Any] | None]:
            async with semaphore:
                try:
                    return fund_code, await get_latest_fund_quote(fund_code, force_refresh=force_refresh)
                except Exception as exc:
                    errors.append(f"{fund_code}: {exc}")
                    return fund_code, None

        for fund_code, quote in await asyncio.gather(*(load_one(code) for code in missing_codes)):
            if quote:
                rows[fund_code] = quote

    if errors and not rows:
        raise RuntimeError("基金行情快照不可用：" + " | ".join(errors[-3:]))
    cache.set(cache_key, rows, min(settings.CACHE_QUOTE_TTL, 60))
    return rows


async def get_fund_holdings(code: str, year: str | None = None, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"fund:holdings:{code}:{year or 'latest'}"
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    now_year = datetime.now().year
    candidates = [str(year)] if year else [str(now_year), str(now_year - 1), str(now_year - 2)]
    last_error: str | None = None
    for candidate in candidates:
        try:
            df = await asyncio.to_thread(ak.fund_portfolio_hold_em, symbol=code, date=candidate)
            if df is None or df.empty:
                continue
            holdings: list[dict[str, Any]] = []
            for _, record in df.iterrows():
                row = record.to_dict()
                holdings.append({
                    "stock_code": str(pick(row, ["股票代码", "代码"], "")),
                    "stock_name": str(pick(row, ["股票名称", "名称"], "")),
                    "hold_ratio": to_float(pick(row, ["占净值比例", "占净值比", "持仓占比"])),
                    "hold_amount": to_float(pick(row, ["持股数", "持股数量"])),
                    "hold_value": to_float(pick(row, ["持仓市值", "市值"])),
                    "quarter": pick(row, ["季度", "报告期"], candidate),
                    "raw": {key: clean_value(value) for key, value in row.items()},
                })
            result = {
                "code": code,
                "year": candidate,
                "count": len(holdings),
                "holdings": holdings,
                "source": "akshare",
            }
            cache.set(cache_key, result, settings.CACHE_FUND_HOLDING_TTL)
            return result
        except Exception as exc:
            last_error = str(exc)
    result = {
        "code": code,
        "year": year or str(now_year - 1),
        "count": 0,
        "holdings": [],
        "source": "akshare",
        "warning": "未取得持仓数据，可能是基金未披露、年份不匹配或 AKShare 接口暂不可用。",
        "error": last_error,
    }
    cache.set(cache_key, result, 3600)
    return result


def _report_key(value: Any) -> tuple[int, int]:
    text = str(clean_value(value) or "")
    match = re.search(r"(\d{4}).*?([1-4])\s*季度", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d{4})[-/年](\d{1,2})", text)
    if match:
        month = int(match.group(2))
        return int(match.group(1)), max(1, min(4, math.ceil(month / 3)))
    match = re.search(r"(\d{4})", text)
    if match:
        return int(match.group(1)), 4
    return 0, 0


def _latest_report_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], tuple[int, int]]:
    keyed = [(item, _report_key(item.get("quarter"))) for item in items]
    valid_keys = [key for _, key in keyed if key != (0, 0)]
    if not valid_keys:
        return items, (0, 0)
    latest = max(valid_keys)
    return [item for item, key in keyed if key == latest], latest


def _report_date_from_key(key: tuple[int, int]) -> str | None:
    year, quarter = key
    if not year or not quarter:
        return None
    suffix = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}[quarter]
    return f"{year}{suffix}"


def _report_date_candidates(preferred: str | None = None) -> list[str]:
    today = date.today()
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred.replace("-", ""))
    for year in range(today.year, today.year - 4, -1):
        for suffix in ["1231", "0930", "0630", "0331"]:
            candidate = f"{year}{suffix}"
            try:
                candidate_date = datetime.strptime(candidate, "%Y%m%d").date()
            except ValueError:
                continue
            if candidate_date <= today and candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _asset_bucket(asset_type: Any) -> str:
    text = str(asset_type or "")
    if "股票" in text or "权益" in text:
        return "stock"
    if "债" in text:
        return "bond"
    if any(word in text for word in ["银行", "存款", "现金", "货币", "买入返售"]):
        return "bank_cash"
    return "other"


def _summarize_asset_allocation(allocations: list[dict[str, Any]]) -> dict[str, float]:
    summary = {"stock_pct": 0.0, "bond_pct": 0.0, "bank_cash_pct": 0.0, "other_pct": 0.0}
    for item in allocations:
        ratio = to_float(item.get("ratio"))
        if ratio is None:
            continue
        bucket = _asset_bucket(item.get("asset_type"))
        key = f"{bucket}_pct" if bucket != "bank_cash" else "bank_cash_pct"
        summary[key] = round(summary.get(key, 0.0) + ratio, 4)
    return summary


async def get_fund_bond_holdings(code: str, year: str | None = None, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"fund:bond_holdings:{code}:{year or 'latest'}"
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    fetcher = getattr(ak, "fund_portfolio_bond_hold_em", None)
    if fetcher is None:
        result = {
            "code": code,
            "year": year,
            "count": 0,
            "holdings": [],
            "source": "akshare",
            "warning": "当前 AKShare 版本未提供 fund_portfolio_bond_hold_em，债券明细暂不可用。",
        }
        cache.set(cache_key, result, settings.CACHE_FUND_HOLDING_TTL)
        return result
    now_year = datetime.now().year
    candidates = [str(year)] if year else [str(now_year), str(now_year - 1), str(now_year - 2)]
    last_error: str | None = None
    for candidate in candidates:
        try:
            df = await asyncio.to_thread(fetcher, symbol=code, date=candidate)
            if df is None or df.empty:
                continue
            holdings: list[dict[str, Any]] = []
            for _, record in df.iterrows():
                row = record.to_dict()
                values = list(row.values())
                holdings.append(
                    {
                        "bond_code": str(pick(row, ["债券代码", "代码"], values[0] if values else "")),
                        "bond_name": str(pick(row, ["债券名称", "名称"], values[1] if len(values) > 1 else "")),
                        "hold_ratio": to_float(pick(row, ["占净值比例", "占净值比", "持仓占比"], values[2] if len(values) > 2 else None)),
                        "hold_value": to_float(pick(row, ["持仓市值", "市值"], values[-1] if values else None)),
                        "quarter": pick(row, ["季度", "报告期"], candidate),
                        "raw": {key: clean_value(value) for key, value in row.items()},
                    }
                )
            result = {
                "code": code,
                "year": candidate,
                "count": len(holdings),
                "holdings": holdings,
                "source": "akshare",
            }
            cache.set(cache_key, result, settings.CACHE_FUND_HOLDING_TTL)
            return result
        except Exception as exc:
            last_error = str(exc)
    result = {
        "code": code,
        "year": year or str(now_year - 1),
        "count": 0,
        "holdings": [],
        "source": "akshare",
        "warning": "未取得债券持仓明细，可能是基金未披露、年份不匹配或 AKShare 接口暂不可用。",
        "error": last_error,
    }
    cache.set(cache_key, result, 3600)
    return result


async def get_fund_asset_allocation(code: str, report_date: str | None = None, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"fund:asset_allocation:{code}:{report_date or 'latest'}"
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    fetcher = getattr(ak, "fund_individual_detail_hold_xq", None)
    if fetcher is None:
        return {
            "code": code,
            "allocations": [],
            "summary": {},
            "source": "akshare",
            "warning": "当前 AKShare 版本未提供 fund_individual_detail_hold_xq，资产配置将由持仓明细估算。",
        }

    errors: list[str] = []
    for candidate in _report_date_candidates(report_date):
        try:
            df = await asyncio.to_thread(fetcher, symbol=code, date=candidate)
            if df is None or df.empty:
                continue
            allocations: list[dict[str, Any]] = []
            for _, record in df.iterrows():
                row = record.to_dict()
                values = list(row.values())
                asset_type = pick(row, ["资产类型", "类型", "项目", "资产"], values[0] if values else "")
                ratio = to_float(pick(row, ["仓位占比", "占净值比例", "占比", "比例"], values[1] if len(values) > 1 else None))
                if asset_type:
                    allocations.append(
                        {
                            "asset_type": str(asset_type),
                            "ratio": ratio,
                            "raw": {key: clean_value(value) for key, value in row.items()},
                        }
                    )
            if allocations:
                result = {
                    "code": code,
                    "report_date": candidate,
                    "allocations": allocations,
                    "summary": _summarize_asset_allocation(allocations),
                    "source": "akshare",
                }
                cache.set(cache_key, result, settings.CACHE_FUND_HOLDING_TTL)
                return result
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")

    return {
        "code": code,
        "report_date": report_date,
        "allocations": [],
        "summary": {},
        "source": "akshare",
        "warning": "未取得资产配置披露，资产比例将由股票/债券明细加总估算。",
        "error": " | ".join(errors[-3:]) if errors else None,
    }


async def _get_bond_quotes_map(codes: list[str], force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    unique_codes = sorted({str(code).strip() for code in codes if str(code).strip()})
    if not unique_codes:
        return {}
    cache_key = "bond:quotes:" + ",".join(unique_codes)
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    fetcher = getattr(ak, "bond_zh_hs_spot", None)
    if fetcher is None:
        return {}
    df = await asyncio.to_thread(fetcher)
    if df is None or df.empty:
        return {}
    code_col = next((name for name in ["代码", "债券代码", "symbol"] if name in df.columns), None)
    if code_col is None:
        return {}
    target = set(unique_codes)
    rows: dict[str, dict[str, Any]] = {}
    matched = df[df[code_col].astype(str).isin(target)]
    for _, record in matched.iterrows():
        row = {key: clean_value(value) for key, value in record.to_dict().items()}
        bond_code = str(row.get(code_col) or "").strip()
        row.update(
            {
                "code": bond_code,
                "name": pick(row, ["名称", "债券名称", "证券简称"]),
                "latest_price": to_float(pick(row, ["最新价", "最新", "收盘"])),
                "change_pct": to_float(pick(row, ["涨跌幅", "涨幅", "涨跌幅%"])),
                "source": "akshare",
            }
        )
        rows[bond_code] = row
    cache.set(cache_key, rows, min(settings.CACHE_QUOTE_TTL, 60))
    return rows


def _derived_asset_allocation(
    stock_items: list[dict[str, Any]],
    bond_items: list[dict[str, Any]],
) -> dict[str, Any]:
    stock_pct = round(sum(to_float(item.get("hold_ratio")) or 0 for item in stock_items), 4)
    bond_pct = round(sum(to_float(item.get("hold_ratio")) or 0 for item in bond_items), 4)
    bank_cash_pct = round(max(100 - stock_pct - bond_pct, 0), 4)
    return {
        "summary": {
            "stock_pct": stock_pct,
            "bond_pct": bond_pct,
            "bank_cash_pct": bank_cash_pct,
            "other_pct": 0.0,
        },
        "source": "derived_from_disclosed_holdings",
        "warning": "未取得资产配置披露，股票/债券比例由已披露明细加总，银行存款/现金为剩余比例估算。",
    }


def _coverage_level(coverage_ratio: float, asset_coverage_ratio: float) -> str:
    score = max(coverage_ratio, asset_coverage_ratio)
    if score >= 80:
        return "较高"
    if score >= 45:
        return "中等"
    if score > 0:
        return "较低"
    return "不可估"


def _is_a_share_code(value: Any) -> bool:
    return bool(re.fullmatch(r"\d{6}", str(value or "").strip()))


async def get_fund_realtime_estimate(code: str, force_refresh: bool = False) -> dict[str, Any]:
    """用披露持仓和实时行情近似估算基金当日涨跌。

    估算值不等于官方净值：基金持仓披露有滞后，债券/现金/QDII/费用/汇率等不会被完全覆盖。
    """
    cache_key = f"fund:realtime_estimate:{code}"
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    quote, stock_holdings, bond_holdings = await asyncio.gather(
        get_latest_fund_quote(code, force_refresh=force_refresh),
        get_fund_holdings(code, force_refresh=force_refresh),
        get_fund_bond_holdings(code, force_refresh=force_refresh),
    )
    latest_stock_items, stock_key = _latest_report_items(stock_holdings.get("holdings", []))
    latest_bond_items, bond_key = _latest_report_items(bond_holdings.get("holdings", []))
    latest_key = max(stock_key, bond_key)
    report_date = _report_date_from_key(latest_key)
    allocation = await get_fund_asset_allocation(code, report_date=report_date, force_refresh=force_refresh)
    allocation_summary = allocation.get("summary") or {}
    if not allocation_summary:
        allocation = {**allocation, **_derived_asset_allocation(latest_stock_items, latest_bond_items)}
        allocation_summary = allocation["summary"]

    raw_stock_codes = [str(item.get("stock_code") or "").strip() for item in latest_stock_items if item.get("stock_code")]
    has_non_a_share_stock = any(not _is_a_share_code(stock_code) for stock_code in raw_stock_codes)
    stock_codes = [stock_code for stock_code in raw_stock_codes if _is_a_share_code(stock_code)]
    from app.data.akshare_stock import get_stock_quotes_map

    try:
        stock_quotes = await get_stock_quotes_map(stock_codes, force_refresh=force_refresh)
        stock_quote_error = None
    except Exception as exc:
        stock_quotes = {}
        stock_quote_error = str(exc)

    stock_contributors: list[dict[str, Any]] = []
    stock_direct_contribution = 0.0
    covered_stock_ratio = 0.0
    disclosed_stock_ratio = 0.0
    for item in latest_stock_items:
        stock_code = str(item.get("stock_code") or "").strip()
        hold_ratio = to_float(item.get("hold_ratio"))
        if hold_ratio is None or hold_ratio <= 0:
            continue
        disclosed_stock_ratio += hold_ratio
        quote_row = stock_quotes.get(stock_code, {}) if _is_a_share_code(stock_code) else {}
        change_pct = to_float(quote_row.get("change_pct"))
        contribution_pct = None
        if change_pct is not None:
            covered_stock_ratio += hold_ratio
            contribution_pct = round(hold_ratio * change_pct / 100, 4)
            stock_direct_contribution += contribution_pct
        stock_contributors.append(
            {
                "stock_code": stock_code,
                "stock_name": item.get("stock_name") or quote_row.get("name"),
                "hold_ratio": round(hold_ratio, 4),
                "change_pct": change_pct,
                "contribution_pct": contribution_pct,
                "latest_price": quote_row.get("latest_price"),
                "quote_source": quote_row.get("source"),
            }
        )

    stock_allocation_pct = to_float(allocation_summary.get("stock_pct")) or disclosed_stock_ratio
    other_pct = round(to_float(allocation_summary.get("other_pct")) or 0.0, 4)
    wrapper_like_allocation = other_pct > 50 and stock_allocation_pct < 30
    stock_scale = 1.0
    can_scale_stock = (
        covered_stock_ratio > 0
        and stock_allocation_pct > covered_stock_ratio
        and not has_non_a_share_stock
        and not wrapper_like_allocation
        and covered_stock_ratio / max(stock_allocation_pct, 1) >= 0.2
    )
    if can_scale_stock:
        stock_scale = stock_allocation_pct / covered_stock_ratio
    stock_estimated_contribution = round(stock_direct_contribution * stock_scale, 4)
    uncovered_stock_ratio = round(max(stock_allocation_pct - covered_stock_ratio, 0), 4)

    bond_codes = [str(item.get("bond_code") or "").strip() for item in latest_bond_items if item.get("bond_code")]
    try:
        bond_quotes = await _get_bond_quotes_map(bond_codes, force_refresh=force_refresh)
        bond_quote_error = None
    except Exception as exc:
        bond_quotes = {}
        bond_quote_error = str(exc)

    bond_contributors: list[dict[str, Any]] = []
    bond_direct_contribution = 0.0
    covered_bond_ratio = 0.0
    disclosed_bond_ratio = 0.0
    for item in latest_bond_items:
        bond_code = str(item.get("bond_code") or "").strip()
        hold_ratio = to_float(item.get("hold_ratio"))
        if hold_ratio is None or hold_ratio <= 0:
            continue
        disclosed_bond_ratio += hold_ratio
        quote_row = bond_quotes.get(bond_code, {})
        change_pct = to_float(quote_row.get("change_pct"))
        contribution_pct = None
        if change_pct is not None:
            covered_bond_ratio += hold_ratio
            contribution_pct = round(hold_ratio * change_pct / 100, 4)
            bond_direct_contribution += contribution_pct
        bond_contributors.append(
            {
                "bond_code": bond_code,
                "bond_name": item.get("bond_name") or quote_row.get("name"),
                "hold_ratio": round(hold_ratio, 4),
                "change_pct": change_pct,
                "contribution_pct": contribution_pct,
                "latest_price": quote_row.get("latest_price"),
                "quote_source": quote_row.get("source"),
            }
        )

    bond_allocation_pct = to_float(allocation_summary.get("bond_pct")) or disclosed_bond_ratio
    bond_scale = 1.0
    if covered_bond_ratio > 0 and bond_allocation_pct > covered_bond_ratio:
        bond_scale = bond_allocation_pct / covered_bond_ratio
    bond_estimated_contribution = round(bond_direct_contribution * bond_scale, 4)
    bank_cash_pct = round(to_float(allocation_summary.get("bank_cash_pct")) or 0.0, 4)

    quote_coverage_ratio = round(covered_stock_ratio + covered_bond_ratio, 4)
    asset_coverage_ratio = quote_coverage_ratio
    min_coverage_for_full_estimate = 20.0
    can_publish_estimate = quote_coverage_ratio >= min_coverage_for_full_estimate and not wrapper_like_allocation
    direct_estimated_return_pct = round(stock_direct_contribution + bond_direct_contribution, 4)
    full_estimated_return_pct = round(stock_estimated_contribution + bond_estimated_contribution, 4)
    partial_estimate_available = quote_coverage_ratio > 0
    estimated_return_pct = full_estimated_return_pct if can_publish_estimate else direct_estimated_return_pct if partial_estimate_available else None
    estimate_completeness = "full" if can_publish_estimate else "partial" if partial_estimate_available else "unavailable"
    base_nav = to_float(quote.get("latest_nav"))
    estimated_nav = round(base_nav * (1 + estimated_return_pct / 100), 4) if base_nav is not None and estimated_return_pct is not None else None

    warnings: list[str] = [
        "估算基于基金已披露季报持仓，可能与基金经理当前实际仓位不同。",
        "银行存款、现金、费用、申赎冲击、汇率和未披露资产默认不产生实时贡献。",
    ]
    if stock_scale > 1.01:
        warnings.append("已用可取到实时行情的股票平均涨跌，外推到披露的股票资产比例。")
    if has_non_a_share_stock:
        warnings.append("持仓包含海外或非 A 股代码，未把 A 股涨跌外推到海外仓位。")
    if wrapper_like_allocation:
        warnings.append("该基金大部分资产为其他/基金类资产，无法仅用股票持仓估算完整净值涨跌。")
    if not can_publish_estimate:
        warnings.append(f"实时行情覆盖 {quote_coverage_ratio:.2f}% 低于 {min_coverage_for_full_estimate:.0f}% 阈值，暂不发布完整基金估值。")
    if estimate_completeness == "partial":
        warnings.append("已按可取得实时行情的披露持仓计算部分估值，未覆盖资产不参与本次估算。")
    if bond_allocation_pct > 0 and covered_bond_ratio == 0:
        warnings.append("债券持仓未取得可用实时涨跌幅，债券贡献暂按 0 处理。")
    if "QDII" in str((quote.get("name") or "")).upper() or any("QDII" in str(value).upper() for value in quote.values() if isinstance(value, str)):
        warnings.append("QDII/海外资产行情、汇率和时区差异不在本 A 股持仓估算中完整覆盖。")
    if stock_quote_error:
        warnings.append(f"A 股实时行情暂不可用：{stock_quote_error[:160]}")
    if bond_quote_error:
        warnings.append(f"债券实时行情暂不可用：{bond_quote_error[:160]}")
    for source_warning in [stock_holdings.get("warning"), bond_holdings.get("warning"), allocation.get("warning")]:
        if source_warning and source_warning not in warnings:
            warnings.append(source_warning)

    stock_contributors.sort(key=lambda row: abs(row.get("contribution_pct") or 0), reverse=True)
    bond_contributors.sort(key=lambda row: abs(row.get("contribution_pct") or 0), reverse=True)
    result = {
        "code": code,
        "estimated_return_pct": estimated_return_pct,
        "estimated_nav": estimated_nav,
        "estimate_completeness": estimate_completeness,
        "base_nav": base_nav,
        "official_daily_return": quote.get("daily_return"),
        "nav_date": quote.get("nav_date"),
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare_holdings_and_realtime_quotes",
        "method": "披露持仓权重 * 实时涨跌幅；仅在覆盖率充足且不含海外/联接类资产时外推，现金/银行存款及无行情资产按 0 处理。",
        "asset_allocation": {
            "stock_pct": round(stock_allocation_pct, 4),
            "bond_pct": round(bond_allocation_pct, 4),
            "bank_cash_pct": bank_cash_pct,
            "other_pct": other_pct,
            "report_date": allocation.get("report_date") or report_date,
            "source": allocation.get("source"),
            "items": allocation.get("allocations", []),
        },
        "coverage": {
            "stock_disclosed_ratio": round(disclosed_stock_ratio, 4),
            "stock_quote_covered_ratio": round(covered_stock_ratio, 4),
            "uncovered_stock_ratio": uncovered_stock_ratio,
            "bond_disclosed_ratio": round(disclosed_bond_ratio, 4),
            "bond_quote_covered_ratio": round(covered_bond_ratio, 4),
            "quote_coverage_ratio": quote_coverage_ratio,
            "asset_coverage_ratio": asset_coverage_ratio,
            "confidence": _coverage_level(quote_coverage_ratio, asset_coverage_ratio),
        },
        "contribution": {
            "stock_direct_pct": round(stock_direct_contribution, 4),
            "stock_estimated_pct": stock_estimated_contribution,
            "direct_estimated_pct": direct_estimated_return_pct,
            "full_estimated_pct": full_estimated_return_pct,
            "bond_direct_pct": round(bond_direct_contribution, 4),
            "bond_estimated_pct": bond_estimated_contribution,
            "bank_cash_pct": 0.0,
            "other_pct": 0.0,
        },
        "stock_contributors": stock_contributors,
        "bond_contributors": bond_contributors,
        "warnings": warnings,
        "data_quality": {
            "stock_holding_year": stock_holdings.get("year"),
            "bond_holding_year": bond_holdings.get("year"),
            "latest_report_key": {"year": latest_key[0] or None, "quarter": latest_key[1] or None},
            "stock_quote_count": len(stock_quotes),
            "bond_quote_count": len(bond_quotes),
        },
    }
    cache.set(cache_key, result, settings.CACHE_FUND_ESTIMATE_TTL)
    return result


async def get_fund_realtime_estimates(codes: list[str], force_refresh: bool = False) -> dict[str, Any]:
    """Batch estimate fund intraday returns for portfolio and watchlist screens.

    Low-frequency disclosure data is cached inside each single-fund estimate, and
    the A-share market snapshot is shared by get_stock_quotes_map for 30 seconds.
    """
    unique_codes = sorted({str(code).strip().zfill(6) for code in codes if str(code).strip()})
    if not unique_codes:
        return {
            "count": 0,
            "estimates": {},
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ttl_seconds": settings.CACHE_FUND_ESTIMATE_TTL,
            "stock_quote_ttl_seconds": settings.CACHE_STOCK_QUOTE_TTL,
            "holding_ttl_seconds": settings.CACHE_FUND_HOLDING_TTL,
        }

    cache_key = "fund:realtime_estimates:" + ",".join(unique_codes)
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    semaphore = asyncio.Semaphore(2)

    async def load_one(fund_code: str) -> tuple[str, dict[str, Any]]:
        async with semaphore:
            try:
                return fund_code, await get_fund_realtime_estimate(fund_code, force_refresh=force_refresh)
            except Exception as exc:
                return fund_code, {
                    "code": fund_code,
                    "estimated_return_pct": None,
                    "estimated_nav": None,
                    "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "error",
                    "warnings": [str(exc)[:300]],
                }

    pairs = await asyncio.gather(*(load_one(code) for code in unique_codes))
    estimates = {code: estimate for code, estimate in pairs}
    result = {
        "count": len(estimates),
        "estimates": estimates,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ttl_seconds": settings.CACHE_FUND_ESTIMATE_TTL,
        "stock_quote_ttl_seconds": settings.CACHE_STOCK_QUOTE_TTL,
        "holding_ttl_seconds": settings.CACHE_FUND_HOLDING_TTL,
        "method": "批量复用披露持仓缓存和 A 股全市场实时快照，按基金持仓权重估算当日涨跌。",
    }
    cache.set(cache_key, result, settings.CACHE_FUND_ESTIMATE_TTL)
    return result


async def get_fund_realtime_estimate_isolated(code: str, force_refresh: bool = False) -> dict[str, Any]:
    payload = await get_fund_realtime_estimates_isolated([code], force_refresh=force_refresh)
    normalized = str(code).strip().zfill(6)
    estimate = (payload.get("estimates") or {}).get(normalized)
    if estimate:
        return estimate
    return {
        "code": normalized,
        "estimated_return_pct": None,
        "estimated_nav": None,
        "as_of": payload.get("as_of"),
        "source": "error",
        "warnings": ["未取得该基金估值结果。"],
    }


async def get_fund_realtime_estimates_isolated(codes: list[str], force_refresh: bool = False) -> dict[str, Any]:
    unique_codes = sorted({str(code).strip().zfill(6) for code in codes if str(code).strip()})
    if not unique_codes:
        return await get_fund_realtime_estimates(unique_codes, force_refresh=force_refresh)
    if os.getenv("STARMAP_FUND_ESTIMATE_DIRECT", "").lower() in {"1", "true", "yes"}:
        return await get_fund_realtime_estimates(unique_codes, force_refresh=force_refresh)

    cache_key = "fund:realtime_estimates_isolated:" + ",".join(unique_codes)
    stale_key = cache_key + ":last_success"
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = await asyncio.to_thread(_fetch_fund_estimates_subprocess, unique_codes)
        cache.set(cache_key, result, settings.CACHE_FUND_ESTIMATE_TTL)
        cache.set(stale_key, result, 10 * 60)
        return result
    except Exception as exc:
        stale = cache.get(stale_key)
        if stale:
            result = {
                **stale,
                "warning": f"本次估值子进程刷新失败，暂用最近一次成功估值：{str(exc)[:160]}",
                "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            cache.set(cache_key, result, min(settings.CACHE_FUND_ESTIMATE_TTL, 10))
            return result

        if len(unique_codes) > 1:
            retry_estimates: dict[str, Any] = {}
            retry_errors: list[str] = []
            for single_code in unique_codes:
                try:
                    single_payload = await asyncio.to_thread(_fetch_fund_estimates_subprocess, [single_code])
                    single_estimate = (single_payload.get("estimates") or {}).get(single_code)
                    if single_estimate:
                        retry_estimates[single_code] = single_estimate
                        continue
                    retry_errors.append(f"{single_code}: 未取得估值结果")
                except Exception as single_exc:
                    retry_errors.append(f"{single_code}: {str(single_exc)[:120]}")
                    retry_estimates[single_code] = {
                        "code": single_code,
                        "estimated_return_pct": None,
                        "estimated_nav": None,
                        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "error",
                        "warnings": [f"单只估值子进程失败：{str(single_exc)[:180]}"],
                    }
            if retry_estimates:
                result = {
                    "count": len(retry_estimates),
                    "estimates": retry_estimates,
                    "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ttl_seconds": min(settings.CACHE_FUND_ESTIMATE_TTL, 10),
                    "stock_quote_ttl_seconds": settings.CACHE_STOCK_QUOTE_TTL,
                    "holding_ttl_seconds": settings.CACHE_FUND_HOLDING_TTL,
                    "source": "isolated_retry",
                    "warning": "批量估值子进程失败，已逐只隔离重试；" + "；".join(retry_errors[:3]),
                }
                cache.set(cache_key, result, min(settings.CACHE_FUND_ESTIMATE_TTL, 10))
                cache.set(stale_key, result, 10 * 60)
                return result

        estimates = {
            code: {
                "code": code,
                "estimated_return_pct": None,
                "estimated_nav": None,
                "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "error",
                "warnings": [f"估值子进程失败：{str(exc)[:240]}"],
            }
            for code in unique_codes
        }
        result = {
            "count": len(estimates),
            "estimates": estimates,
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ttl_seconds": min(settings.CACHE_FUND_ESTIMATE_TTL, 10),
            "stock_quote_ttl_seconds": settings.CACHE_STOCK_QUOTE_TTL,
            "holding_ttl_seconds": settings.CACHE_FUND_HOLDING_TTL,
            "source": "error",
            "warning": str(exc)[:500],
        }
        cache.set(cache_key, result, min(settings.CACHE_FUND_ESTIMATE_TTL, 10))
        return result


def _fetch_fund_estimates_subprocess(unique_codes: list[str]) -> dict[str, Any]:
    script = r'''
import asyncio
import json
import os
import sys

os.environ["STARMAP_FUND_ESTIMATE_DIRECT"] = "1"
from app.data.akshare_fund import get_fund_realtime_estimates

async def main():
    codes = json.loads(sys.argv[1])
    result = await get_fund_realtime_estimates(codes, force_refresh=True)
    print(json.dumps(result, ensure_ascii=False))

asyncio.run(main())
'''
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "STARMAP_FUND_ESTIMATE_DIRECT": "1"}
    completed = subprocess.run(
        [sys.executable, "-c", script, json.dumps(unique_codes, ensure_ascii=False)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(stderr[-1000:] or f"fund estimate subprocess exited with {completed.returncode}")
    stdout = (completed.stdout or "").strip()
    if not stdout:
        raise RuntimeError("fund estimate subprocess returned empty output")
    return json.loads(stdout.splitlines()[-1])


async def compare_funds(codes: list[str], force_refresh: bool = False) -> dict[str, Any]:
    funds = [await get_fund_detail(code, force_refresh=force_refresh) for code in codes]
    return {
        "count": len(funds),
        "funds": funds,
        "source": "akshare_with_fallback",
    }


def classify_risk(fund_type: str | None, volatility: float | None = None) -> str:
    text = (fund_type or "").upper()
    if "债" in text or "货币" in text:
        return "偏低"
    if "QDII" in text or "股票" in text or "指数" in text:
        if volatility is not None and volatility < 12:
            return "中等"
        return "偏高"
    if "混合" in text:
        return "中等"
    return "中等"


def score_rank_record(record: dict[str, Any], risk_preference: str = "balanced") -> float:
    """Risk-adjusted candidate score, not a raw performance ranking."""
    risk_preference = risk_preference.lower()
    year_return = float(record.get("year_return") or 0)
    six_month_return = float(record.get("six_month_return") or 0)
    three_month_return = float(record.get("three_month_return") or 0)
    month_return = float(record.get("month_return") or 0)
    week_return = float(record.get("week_return") or 0)
    daily_return = float(record.get("daily_return") or 0)
    this_year_return = float(record.get("this_year_return") or 0)

    def cap(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    medium_term = (
        cap(six_month_return, -20, 45) * 0.28
        + cap(three_month_return, -15, 30) * 0.24
        + cap(month_return, -8, 12) * 0.16
        + cap(year_return, -25, 60) * 0.16
    )
    persistence_bonus = 0.0
    if six_month_return > 0:
        persistence_bonus += 4
    if three_month_return > 0:
        persistence_bonus += 3
    if month_return > -3:
        persistence_bonus += 2
    if this_year_return > 0:
        persistence_bonus += 1.5

    chase_penalty = 0.0
    chase_penalty += max(daily_return - 3, 0) * 3.0
    chase_penalty += max(week_return - 8, 0) * 1.2
    chase_penalty += max(month_return - 18, 0) * 1.4
    chase_penalty += max(year_return - 80, 0) * 0.65
    chase_penalty += max(abs(daily_return) - 6, 0) * 1.6
    valuation_penalty = max(year_return - 50, 0) * 0.4 + max(three_month_return - 35, 0) * 0.5 + max(month_return - 14, 0) * 0.8
    reversal_penalty = max(six_month_return, 0) * 0.15 if month_return < -5 else 0.0

    if risk_preference in {"conservative", "稳健"}:
        score = medium_term + persistence_bonus - chase_penalty * 1.35 - valuation_penalty * 1.2 - abs(daily_return) * 0.8 - reversal_penalty
    elif risk_preference in {"aggressive", "进取"}:
        score = medium_term * 1.12 + persistence_bonus - chase_penalty * 0.75 - valuation_penalty * 0.35 - reversal_penalty * 0.6
    else:
        score = medium_term + persistence_bonus - chase_penalty - valuation_penalty - reversal_penalty
    return round(float(score), 4)


async def get_fund_recommend_universe(fund_type: str = "全部", force_refresh: bool = False) -> dict[str, Any]:
    normalized_type = normalize_fund_type(fund_type)
    key = f"fund:recommend_universe:{normalized_type}"
    cached = None if force_refresh else cache.get(key)
    if cached is not None:
        return cached
    try:
        df = await asyncio.to_thread(ak.fund_open_fund_rank_em, symbol=normalized_type)
        if df is None or df.empty:
            raise RuntimeError("AKShare fund_open_fund_rank_em returned empty data")
        funds = [_normalize_rank_record(row.to_dict(), normalized_type) for _, row in df.iterrows()]
        result = {
            "fund_type": normalized_type,
            "count": len(funds),
            "funds": funds,
            "source": "akshare",
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cache.set(key, result, settings.CACHE_RANK_TTL)
        return result
    except Exception as exc:
        fallback = _fallback_rank(normalized_type, 100)
        fallback["warning"] = f"推荐全量池不可用，已降级到内置样例：{exc}"
        return fallback


def is_chasing_candidate(record: dict[str, Any], risk_preference: str) -> bool:
    daily_return = float(record.get("daily_return") or 0)
    week_return = float(record.get("week_return") or 0)
    month_return = float(record.get("month_return") or 0)
    three_month_return = float(record.get("three_month_return") or 0)
    year_return = float(record.get("year_return") or 0)
    if risk_preference.lower() in {"aggressive", "进取"}:
        return daily_return > 6 or week_return > 14 or month_return > 32 or year_return > 160
    return daily_return > 4.5 or week_return > 10 or month_return > 18 or three_month_return > 40 or year_return > 80


def fund_series_key(record: dict[str, Any]) -> str:
    name = str(record.get("name") or "")
    return re.sub(r"[\s（）()]*[A-Z]$|[\s（）()]*[A-Z]类$", "", name).strip() or str(record.get("code") or "")


async def recommend_funds(
    fund_type: str = "QDII",
    risk_preference: str = "balanced",
    top_n: int = 5,
    force_refresh: bool = False,
) -> dict[str, Any]:
    rank = await get_fund_recommend_universe(fund_type=fund_type, force_refresh=force_refresh)
    candidates: list[dict[str, Any]] = []
    chasing: list[dict[str, Any]] = []
    seen_series: set[str] = set()
    for record in rank.get("funds", []):
        if is_chasing_candidate(record, risk_preference):
            chasing.append(record)
            continue
        series_key = fund_series_key(record)
        if series_key in seen_series:
            continue
        seen_series.add(series_key)
        enriched = dict(record)
        enriched["score"] = score_rank_record(record, risk_preference)
        enriched["risk_level"] = classify_risk(enriched.get("fund_type"))
        enriched["reasons"] = [
            "中长期收益指标在候选池内靠前" if (enriched.get("year_return") or 0) > 0 else "近期收益指标需要结合回撤再确认",
            "适合作为基金比较候选，不应单独作为买入依据",
            "后续需要查看持仓集中度、费率和净值回撤",
        ]
        enriched["risks"] = [
            "历史收益不代表未来表现",
            "QDII 还会受到汇率、海外市场时区和申赎额度影响" if normalize_fund_type(fund_type) == "QDII" else "需要关注行业集中和风格漂移",
        ]
        candidates.append(enriched)
    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    result = {
        "fund_type": normalize_fund_type(fund_type),
        "risk_preference": risk_preference,
        "count": len(candidates[:top_n]),
        "funds": candidates[:top_n],
        "source": rank.get("source", "akshare"),
        "as_of": rank.get("as_of"),
        "method": "基于 AKShare 排名指标的多周期收益打分，LLM 只负责解释，不直接预测涨跌。",
    }
    if rank.get("warning"):
        result["warning"] = rank["warning"]
    return result
