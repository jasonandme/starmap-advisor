"""AKShare 股票数据封装，作为基金持仓分析的辅助层。"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import akshare as ak

from app.config import get_settings
from app.data.akshare_fund import clean_value, to_float
from app.data.cache import cache


settings = get_settings()


def _pick(row: dict[str, Any], names: list[str], default: Any = None) -> Any:
    for name in names:
        if name in row:
            value = clean_value(row[name])
            if value is not None:
                return value
    return default


def _normalize_code(value: Any) -> str:
    text = str(clean_value(value) or "").strip()
    match = re.search(r"(\d{6})$", text)
    if match:
        return match.group(1)
    return text.zfill(6) if text.isdigit() else text


async def get_stock_quotes_map(codes: list[str], force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """批量获取 A 股实时行情，避免同一次基金估算里重复拉全市场快照。"""
    unique_codes = sorted({_normalize_code(code) for code in codes if code})
    if not unique_codes:
        return {}
    key = "stock:quotes:" + ",".join(unique_codes)
    cached = None if force_refresh else cache.get(key)
    if cached is not None:
        return cached

    all_key = "stock:quotes:all"
    all_cached = None if force_refresh else cache.get(all_key)
    if all_cached is not None:
        rows = {code: all_cached[code] for code in unique_codes if code in all_cached}
        cache.set(key, rows, settings.CACHE_STOCK_QUOTE_TTL)
        return rows

    try:
        rows = await asyncio.to_thread(_fetch_stock_quotes_eastmoney, unique_codes)
        cache.set(key, rows, settings.CACHE_STOCK_QUOTE_TTL)
        return rows
    except Exception:
        pass

    if os.getenv("STARMAP_STOCK_QUOTE_DIRECT", "").lower() not in {"1", "true", "yes"}:
        payload = await asyncio.to_thread(_fetch_stock_quotes_subprocess, unique_codes)
        rows = payload.get("rows", {})
        all_rows = payload.get("all_rows", {})
        if all_rows:
            cache.set(all_key, all_rows, settings.CACHE_STOCK_QUOTE_TTL)
        cache.set(key, rows, settings.CACHE_STOCK_QUOTE_TTL)
        return rows

    rows, all_rows = _fetch_stock_quotes_direct(unique_codes)
    cache.set(all_key, all_rows, settings.CACHE_STOCK_QUOTE_TTL)
    cache.set(key, rows, settings.CACHE_STOCK_QUOTE_TTL)
    return rows


def _fetch_stock_quotes_direct(unique_codes: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    df = None
    source_name = "akshare_stock_zh_a_spot_em"
    for fetcher_name in ["stock_zh_a_spot_em", "stock_zh_a_spot"]:
        try:
            fetched = getattr(ak, fetcher_name)()
            if fetched is not None and not fetched.empty:
                df = fetched
                source_name = f"akshare_{fetcher_name}"
                break
            errors.append(f"{fetcher_name}: empty")
        except Exception as exc:
            errors.append(f"{fetcher_name}: {exc}")
    if df is None or df.empty:
        raise RuntimeError("A 股实时行情不可用：" + " | ".join(errors[-2:]))
    code_col = next((name for name in ["代码", "股票代码", "证券代码", "symbol", "code"] if name in df.columns), None)
    if code_col is None:
        raise RuntimeError("A 股行情缺少代码列")

    target = set(unique_codes)
    all_rows: dict[str, dict[str, Any]] = {}
    for _, record in df.iterrows():
        raw = {key: clean_value(value) for key, value in record.to_dict().items()}
        code = _normalize_code(raw.get(code_col))
        raw.update(
            {
                "code": code,
                "name": _pick(raw, ["名称", "股票名称", "证券简称", "name"]),
                "latest_price": to_float(_pick(raw, ["最新价", "最新", "收盘", "trade"])),
                "change_pct": to_float(_pick(raw, ["涨跌幅", "涨幅", "涨跌幅%", "changepercent"])),
                "turnover_rate": to_float(_pick(raw, ["换手率", "turnoverratio"])),
                "amount": to_float(_pick(raw, ["成交额", "amount"])),
                "source": source_name,
            }
        )
        if code:
            all_rows[code] = raw
    rows = {code: all_rows[code] for code in target if code in all_rows}
    return rows, all_rows


def _eastmoney_market_prefix(code: str) -> str:
    return "1" if code.startswith("6") else "0"


def _fetch_stock_quotes_eastmoney(unique_codes: list[str]) -> dict[str, dict[str, Any]]:
    secids = ",".join(f"{_eastmoney_market_prefix(code)}.{code}" for code in unique_codes)
    query = urlencode(
        {
            "fltt": "2",
            "invt": "2",
            "fields": "f12,f14,f2,f3,f6,f8",
            "secids": secids,
        }
    )
    request = Request(
        f"https://push2.eastmoney.com/api/qt/ulist.np/get?{query}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    diff = ((payload.get("data") or {}).get("diff")) or []
    rows: dict[str, dict[str, Any]] = {}
    for item in diff:
        code = _normalize_code(item.get("f12"))
        if not code:
            continue
        rows[code] = {
            "code": code,
            "name": clean_value(item.get("f14")),
            "latest_price": to_float(item.get("f2")),
            "change_pct": to_float(item.get("f3")),
            "turnover_rate": to_float(item.get("f8")),
            "amount": to_float(item.get("f6")),
            "source": "eastmoney_push2",
            "raw": item,
        }
    if not rows:
        raise RuntimeError("东方财富实时行情返回空数据")
    return rows


def _fetch_stock_quotes_subprocess(unique_codes: list[str]) -> dict[str, Any]:
    script = r'''
import json
import os
import sys

os.environ["STARMAP_STOCK_QUOTE_DIRECT"] = "1"
from app.data.akshare_stock import _fetch_stock_quotes_direct

codes = json.loads(sys.argv[1])
rows, all_rows = _fetch_stock_quotes_direct(codes)
print(json.dumps({"rows": rows, "all_rows": all_rows}, ensure_ascii=False))
'''
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "STARMAP_STOCK_QUOTE_DIRECT": "1"}
    completed = subprocess.run(
        [sys.executable, "-c", script, json.dumps(unique_codes, ensure_ascii=False)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(stderr[-800:] or f"stock quote subprocess exited with {completed.returncode}")
    stdout = (completed.stdout or "").strip()
    if not stdout:
        raise RuntimeError("stock quote subprocess returned empty output")
    return json.loads(stdout.splitlines()[-1])


async def get_stock_quote(code: str) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"stock:quote:{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows = await get_stock_quotes_map([code])
    result = rows.get(code)
    if result is None:
        raise LookupError(f"未找到股票 {code}")
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
