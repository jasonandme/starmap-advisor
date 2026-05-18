"""
AKShare 扩展数据接口：基金分红、基金规模、宏观指标。

用于增强基金详情和市场分析的数据维度。
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import akshare as ak

from app.data.akshare_fund import clean_value, to_float, pick
from app.data.cache import cache


def _date_rank(value: Any) -> tuple[int, int, int]:
    text = str(clean_value(value) or "")
    match = re.search(r"(\d{4})[-年/](\d{1,2})(?:[-月/](\d{1,2}))?", text)
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 1))


def _latest_row(df, date_col: str, value_col: str) -> dict[str, Any] | None:
    if df is None or df.empty or date_col not in df.columns or value_col not in df.columns:
        return None
    rows = [record.to_dict() for _, record in df.iterrows() if to_float(record.to_dict().get(value_col)) is not None]
    if not rows:
        return None
    return max(rows, key=lambda row: _date_rank(row.get(date_col)))


async def get_fund_dividend(code: str) -> dict[str, Any]:
    """获取基金分红历史。"""
    cache_key = f"fund:dividend:{code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = await asyncio.to_thread(ak.fund_fh_em, symbol=code)
        if df is None or df.empty:
            return {"code": code, "dividends": [], "source": "akshare", "warning": "暂无分红记录。"}

        dividends: list[dict[str, Any]] = []
        for _, record in df.iterrows():
            row = record.to_dict()
            dividends.append({
                "date": str(clean_value(pick(row, ["权益登记日", "除息日", "日期"], ""))),
                "per_share": to_float(pick(row, ["每份分红", "每10份分红", "分红"])),
                "ex_date": str(clean_value(pick(row, ["除息日"], ""))),
                "pay_date": str(clean_value(pick(row, ["红利发放日", "发放日"], ""))),
                "raw": {k: clean_value(v) for k, v in row.items()},
            })
        result = {
            "code": code,
            "count": len(dividends),
            "dividends": dividends,
            "total_dividends": sum(d.get("per_share") or 0 for d in dividends),
            "source": "akshare",
        }
        cache.set(cache_key, result, 86400)  # 24h cache
        return result
    except Exception as exc:
        return {
            "code": code,
            "dividends": [],
            "source": "akshare",
            "warning": "分红数据暂不可用。",
            "error": str(exc),
        }


async def get_macro_indicators(force_refresh: bool = False) -> dict[str, Any]:
    """获取关键宏观经济指标快照：CPI, PMI。"""
    cache_key = "macro:snapshot"
    cached = None if force_refresh else cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict[str, Any] = {"indicators": {}, "source": "akshare"}

    # CPI
    try:
        df = await asyncio.to_thread(ak.macro_china_cpi_yearly)
        if df is not None and not df.empty:
            latest = _latest_row(df, "日期", "今值")
            if latest:
                result["indicators"]["cpi"] = {
                    "name": "CPI 同比",
                    "value": to_float(latest.get("今值")),
                    "date": str(clean_value(latest.get("日期"))),
                    "unit": "%",
                }
    except Exception as exc:
        result.setdefault("errors", []).append(f"CPI: {exc}")

    # PMI
    try:
        df = await asyncio.to_thread(ak.macro_china_pmi)
        if df is not None and not df.empty:
            latest = _latest_row(df, "月份", "制造业-指数")
            if latest:
                result["indicators"]["pmi"] = {
                    "name": "制造业 PMI",
                    "value": to_float(latest.get("制造业-指数")),
                    "date": str(clean_value(latest.get("月份"))),
                    "unit": "",
                    "threshold": 50,
                    "interpretation": "PMI > 50 扩张，< 50 收缩",
                }
    except Exception as exc:
        result.setdefault("errors", []).append(f"PMI: {exc}")

    # M2
    try:
        df = await asyncio.to_thread(ak.macro_china_money_supply)
        if df is not None and not df.empty:
            latest = _latest_row(df, "月份", "货币和准货币(M2)-同比增长")
            if latest:
                result["indicators"]["m2"] = {
                    "name": "M2 同比",
                    "value": to_float(latest.get("货币和准货币(M2)-同比增长")),
                    "date": str(clean_value(latest.get("月份"))),
                    "unit": "%",
                }
    except Exception as exc:
        result.setdefault("errors", []).append(f"M2: {exc}")

    result["as_of"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cache.set(cache_key, result, 43200)  # 12h cache
    return result
