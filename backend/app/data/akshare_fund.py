"""
AKShare 基金数据接入与指标清洗。

原则：
1. AKShare/东方财富等结构化接口负责拿数据。
2. 本层负责字段归一化、缓存、失败降级和基础指标计算。
3. LLM 只消费这里返回的结构化对象，不直接解析网页。
"""
from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, timedelta
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
    nav = await get_fund_nav(code, force_refresh=force_refresh)
    search = await search_funds(code, limit=5, force_refresh=force_refresh)
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


async def get_fund_holdings(code: str, year: str | None = None) -> dict[str, Any]:
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
            return {
                "code": code,
                "year": candidate,
                "count": len(holdings),
                "holdings": holdings,
                "source": "akshare",
            }
        except Exception as exc:
            last_error = str(exc)
    return {
        "code": code,
        "year": year or str(now_year - 1),
        "count": 0,
        "holdings": [],
        "source": "akshare",
        "warning": "未取得持仓数据，可能是基金未披露、年份不匹配或 AKShare 接口暂不可用。",
        "error": last_error,
    }


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
    risk_preference = risk_preference.lower()
    year_return = record.get("year_return") or 0
    six_month_return = record.get("six_month_return") or 0
    three_month_return = record.get("three_month_return") or 0
    month_return = record.get("month_return") or 0
    daily_return = record.get("daily_return") or 0
    if risk_preference in {"conservative", "稳健"}:
        score = year_return * 0.35 + six_month_return * 0.3 + three_month_return * 0.2 + month_return * 0.1 - abs(daily_return) * 0.5
    elif risk_preference in {"aggressive", "进取"}:
        score = year_return * 0.3 + six_month_return * 0.3 + three_month_return * 0.25 + month_return * 0.15
    else:
        score = year_return * 0.35 + six_month_return * 0.3 + three_month_return * 0.25 + month_return * 0.1
    return round(float(score), 4)


async def recommend_funds(
    fund_type: str = "QDII",
    risk_preference: str = "balanced",
    top_n: int = 5,
    force_refresh: bool = False,
) -> dict[str, Any]:
    rank = await get_fund_rank(fund_type=fund_type, top_n=max(top_n * 8, 30), force_refresh=force_refresh)
    candidates: list[dict[str, Any]] = []
    for record in rank.get("funds", []):
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
