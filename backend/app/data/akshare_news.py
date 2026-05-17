"""财经新闻数据封装。"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from typing import Any

import akshare as ak

from app.data.akshare_fund import clean_value


async def get_stock_news(code: str, limit: int = 10) -> dict[str, Any]:
    df = await asyncio.to_thread(ak.stock_news_em, stock=code)
    if df is None or df.empty:
        return {"code": code, "news": [], "source": "akshare"}
    rows: list[dict[str, Any]] = []
    for _, record in df.head(limit).iterrows():
        rows.append({key: clean_value(value) for key, value in record.to_dict().items()})
    return {"code": code, "news": rows, "source": "akshare"}


async def get_market_flash(limit: int = 20) -> dict[str, Any]:
    """Fetch market flash news in a child process so AKShare JS-engine crashes cannot kill the API."""
    try:
        return await asyncio.to_thread(_fetch_market_flash_isolated, limit)
    except Exception as exc:
        return {
            "news": [],
            "source": "akshare",
            "warning": "财经快讯接口暂不可用，当前分析会改用板块资金、持仓和知识库证据。",
            "error": str(exc),
        }


def _fetch_market_flash_isolated(limit: int) -> dict[str, Any]:
    script = r'''
import json
import sys
import akshare as ak

def clean(value):
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass
    text = str(value)
    return None if text.lower() in {"nan", "nat", "none"} else text

def is_garbled(text):
    if not text:
        return False
    bad_tokens = ["�", "ï¿½", "����"]
    bad_count = sum(text.count(token) for token in bad_tokens)
    return bad_count >= 2 or bad_count / max(len(text), 1) > 0.05

def row_text(row):
    return " ".join(str(value) for value in row.values() if value is not None)

limit = int(sys.argv[1])
errors = []
for source_name, fetcher_name in [
    ("akshare_stock_news_main_cx", "stock_news_main_cx"),
    ("akshare_news_economic_baidu", "news_economic_baidu"),
]:
    try:
        fetcher = getattr(ak, fetcher_name)
        df = fetcher()
        if df is None or df.empty:
            errors.append(f"{source_name}: empty")
            continue
        rows = [
            {key: clean(value) for key, value in record.to_dict().items()}
            for _, record in df.head(limit).iterrows()
        ]
        rows = [row for row in rows if not is_garbled(row_text(row))]
        if not rows:
            errors.append(f"{source_name}: garbled")
            continue
        print(json.dumps({"news": rows, "source": source_name}, ensure_ascii=False))
        raise SystemExit(0)
    except Exception as exc:
        errors.append(f"{source_name}: {exc}")
print(json.dumps({"news": [], "source": "akshare", "warning": "财经快讯接口暂不可用。", "error": " | ".join(errors)}, ensure_ascii=False))
'''
    completed = subprocess.run(
        [sys.executable, "-c", script, str(limit)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=18,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(stderr[-500:] or f"market flash subprocess exited with {completed.returncode}")
    stdout = (completed.stdout or "").strip()
    if not stdout:
        raise RuntimeError("market flash subprocess returned empty output")
    return json.loads(stdout.splitlines()[-1])


async def get_us_market_snapshot(limit: int = 12) -> dict[str, Any]:
    """获取美股代表性股票快照，用于 QDII/海外资产背景判断。"""
    try:
        df = await asyncio.to_thread(ak.stock_us_famous_spot_em)
        if df is None or df.empty:
            return {"items": [], "source": "akshare"}
        rows = [
            {key: clean_value(value) for key, value in record.to_dict().items()}
            for _, record in df.head(limit).iterrows()
        ]
        return {"items": rows, "source": "akshare_stock_us_famous_spot_em"}
    except Exception as exc:
        return {
            "items": [],
            "source": "akshare",
            "warning": "美股快照接口暂不可用。",
            "error": str(exc),
        }
