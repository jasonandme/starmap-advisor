"""AKShare 股票数据封装，作为基金持仓分析的辅助层。"""
from __future__ import annotations

import asyncio
from typing import Any

import akshare as ak

from app.config import get_settings
from app.data.akshare_fund import clean_value
from app.data.cache import cache


settings = get_settings()


async def get_stock_quote(code: str) -> dict[str, Any]:
    key = f"stock:quote:{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
    if df is None or df.empty:
        raise RuntimeError("AKShare stock_zh_a_spot_em 返回空数据")
    matched = df[df["代码"].astype(str) == code]
    if matched.empty:
        raise LookupError(f"未找到股票 {code}")
    result = {
        key: clean_value(value)
        for key, value in matched.iloc[0].to_dict().items()
    }
    result["source"] = "akshare"
    cache.set(key, result, settings.CACHE_QUOTE_TTL)
    return result


async def get_stock_history(code: str, days: int = 120) -> dict[str, Any]:
    df = await asyncio.to_thread(
        ak.stock_zh_a_hist,
        symbol=code,
        period="daily",
        adjust="qfq",
    )
    if df is None or df.empty:
        return {"code": code, "history": [], "source": "akshare"}
    rows = []
    for _, record in df.tail(days).iterrows():
        row = record.to_dict()
        rows.append({key: clean_value(value) for key, value in row.items()})
    return {"code": code, "history": rows, "source": "akshare"}
