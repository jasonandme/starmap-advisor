"""组合持仓、投资偏好与策略建议 API。"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
import asyncio
import time
from datetime import date
from pathlib import Path
from typing import Any

import akshare as ak
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.akshare_fund import get_latest_fund_quote
from app.data.portfolio_seed import SCREENSHOT_HOLDINGS, SCREENSHOT_WATCHLIST
from app.database import get_db
from app.models.portfolio import InvestmentPreference, PortfolioAction, PortfolioImport, PortfolioItem


router = APIRouter(prefix="/api/portfolio", tags=["组合配置"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "portfolio"
FUND_CATALOG_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": []}
KNOWN_FUND_CODE_OVERRIDES: dict[str, dict[str, str]] = {
    "华夏中证电网设备主题ETF联接A": {
        "code": "025856",
        "name": "华夏中证电网设备主题ETF发起式联接A",
        "fund_type": "指数型-股票",
    },
    "南方中证电池主题ETF联接C": {
        "code": "018927",
        "name": "南方中证电池主题ETF发起联接C",
        "fund_type": "指数型-股票",
    },
    "工银瑞信科技智选混合C": {
        "code": "026213",
        "name": "工银科技智选混合C",
        "fund_type": "混合型-偏股",
    },
}


RISK_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "label": "稳健",
        "description": "把回撤和流动性放在第一位，主题基金只作为小比例观察仓。",
        "max_single_fund_pct": 8.0,
        "max_qdii_pct": 18.0,
        "allow_sector_funds": False,
        "max_drawdown_pct": 8.0,
        "max_theme_pct": 18.0,
        "min_cash_pct": 25.0,
        "rebalance_frequency": "monthly",
    },
    "balanced": {
        "label": "均衡",
        "description": "核心资产稳定打底，行业主题和 QDII 做增强。",
        "max_single_fund_pct": 12.0,
        "max_qdii_pct": 30.0,
        "allow_sector_funds": True,
        "max_drawdown_pct": 15.0,
        "max_theme_pct": 40.0,
        "min_cash_pct": 10.0,
        "rebalance_frequency": "monthly",
    },
    "aggressive": {
        "label": "进取",
        "description": "允许更高主题暴露，但必须设置止损、再平衡和仓位上限。",
        "max_single_fund_pct": 18.0,
        "max_qdii_pct": 45.0,
        "allow_sector_funds": True,
        "max_drawdown_pct": 25.0,
        "max_theme_pct": 65.0,
        "min_cash_pct": 5.0,
        "rebalance_frequency": "weekly",
    },
}


GOAL_OPTIONS: dict[str, dict[str, Any]] = {
    "capital_preservation": {
        "label": "稳健防守",
        "target_allocation": [
            {"bucket": "现金/货币/短债", "target_pct": "25%-35%"},
            {"bucket": "宽基/红利/低波", "target_pct": "35%-45%"},
            {"bucket": "养老FOF/偏债", "target_pct": "15%-25%"},
            {"bucket": "行业主题/QDII", "target_pct": "0%-15%"},
        ],
        "rules": ["不追单日大涨", "连续回撤接近阈值时先降仓", "新增主题基金先用观察仓"],
    },
    "balanced_growth": {
        "label": "均衡成长",
        "target_allocation": [
            {"bucket": "核心宽基/FOF", "target_pct": "35%-45%"},
            {"bucket": "行业主题", "target_pct": "25%-40%"},
            {"bucket": "QDII", "target_pct": "15%-30%"},
            {"bucket": "现金/低波", "target_pct": "10%-15%"},
        ],
        "rules": ["主题基金合并看总仓位", "单只基金超过上限只做减法", "每月比较组合与目标仓位"],
    },
    "theme_growth": {
        "label": "进取主题",
        "target_allocation": [
            {"bucket": "强趋势行业", "target_pct": "35%-55%"},
            {"bucket": "核心宽基", "target_pct": "20%-30%"},
            {"bucket": "QDII", "target_pct": "15%-35%"},
            {"bucket": "现金/机动仓", "target_pct": "5%-10%"},
        ],
        "rules": ["主题之间避免高度同质", "单主题分批买入", "触发最大回撤阈值后暂停加仓"],
    },
    "qdii_diversification": {
        "label": "海外分散",
        "target_allocation": [
            {"bucket": "国内核心资产", "target_pct": "45%-60%"},
            {"bucket": "QDII/海外权益", "target_pct": "25%-45%"},
            {"bucket": "行业主题", "target_pct": "10%-25%"},
            {"bucket": "现金/低波", "target_pct": "5%-15%"},
        ],
        "rules": ["关注 QDII 额度和溢价", "避免海外同一指数重复堆仓", "人民币汇率波动纳入复盘"],
    },
    "pension_longterm": {
        "label": "养老长期",
        "target_allocation": [
            {"bucket": "养老FOF/目标日期", "target_pct": "35%-55%"},
            {"bucket": "宽基指数", "target_pct": "20%-35%"},
            {"bucket": "QDII", "target_pct": "10%-25%"},
            {"bucket": "主题基金", "target_pct": "0%-15%"},
        ],
        "rules": ["降低交易频率", "只在仓位明显偏离时再平衡", "主题基金不能挤占长期核心仓"],
    },
}


QDII_KEYWORDS = ("QDII", "全球", "纳斯达克", "标普", "油气", "石油", "海外", "港股通")
THEME_KEYWORDS = (
    "电网",
    "设备",
    "电池",
    "科技",
    "新能源",
    "半导体",
    "军工",
    "煤炭",
    "传媒",
    "房地产",
    "有色",
    "农业",
    "制造",
    "通信",
    "计算机",
    "中药",
    "医疗",
    "食品饮料",
    "证券",
    "碳中和",
    "人工智能",
    "汽车",
    "5G",
)
PENSION_KEYWORDS = ("养老", "FOF", "目标日期")
BROAD_KEYWORDS = ("沪深300", "中证500", "A500", "上证50", "科创50", "创业板", "红利", "低波")


class PortfolioItemRequest(BaseModel):
    fund_code: str = ""
    fund_name: str = Field(min_length=1, max_length=160)
    source: str = "manual"
    amount: float = Field(default=0.0, ge=0)
    yesterday_profit: float | None = None
    holding_profit: float | None = None
    holding_return_pct: float | None = None
    tags: list[str] = []
    is_holding: bool = False
    is_watchlist: bool = True
    notes: str = ""

    @field_validator("fund_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip()
        if value and (not value.isdigit() or len(value) != 6):
            raise ValueError("基金代码需要是 6 位数字；未知代码可留空")
        return value


class PreferenceRequest(BaseModel):
    risk_profile: str = "balanced"
    strategy_goal: str = "balanced_growth"
    max_single_fund_pct: float = Field(default=12.0, ge=1, le=100)
    max_qdii_pct: float = Field(default=30.0, ge=0, le=100)
    allow_sector_funds: bool = True
    max_drawdown_pct: float = Field(default=15.0, ge=1, le=80)
    max_theme_pct: float = Field(default=40.0, ge=0, le=100)
    min_cash_pct: float = Field(default=10.0, ge=0, le=80)
    rebalance_frequency: str = "monthly"
    notes: str = ""

    @field_validator("risk_profile")
    @classmethod
    def validate_risk_profile(cls, value: str) -> str:
        allowed = {"conservative", "balanced", "aggressive", "custom"}
        if value not in allowed:
            raise ValueError("risk_profile 仅支持 conservative/balanced/aggressive/custom")
        return value

    @field_validator("strategy_goal")
    @classmethod
    def validate_strategy_goal(cls, value: str) -> str:
        if value not in GOAL_OPTIONS:
            raise ValueError("未知策略目标")
        return value


class PreferencePatchRequest(BaseModel):
    risk_profile: str | None = None
    strategy_goal: str | None = None
    max_single_fund_pct: float | None = Field(default=None, ge=1, le=100)
    max_qdii_pct: float | None = Field(default=None, ge=0, le=100)
    allow_sector_funds: bool | None = None
    max_drawdown_pct: float | None = Field(default=None, ge=1, le=80)
    max_theme_pct: float | None = Field(default=None, ge=0, le=100)
    min_cash_pct: float | None = Field(default=None, ge=0, le=80)
    rebalance_frequency: str | None = None
    notes: str | None = None
    apply_profile_defaults: bool = False


class PortfolioActionRequest(BaseModel):
    action_type: str = Field(description="auto_invest/buy/sell/switch/analyze/hold")
    amount: float | None = Field(default=None, ge=0)
    target_fund_code: str = ""
    target_fund_name: str = ""
    schedule: str = ""
    status: str = "planned"
    reason: str = ""

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        allowed = {"auto_invest", "buy", "sell", "switch", "analyze", "hold", "pause_auto_invest"}
        if value not in allowed:
            raise ValueError("未知操作类型")
        return value


class ImportTextRequest(BaseModel):
    text: str = Field(min_length=1)
    source_type: str = "holding"


def classify_fund(name: str, extra_tags: list[str] | None = None) -> list[str]:
    tags: list[str] = []
    upper_name = name.upper()
    if any(keyword in upper_name for keyword in QDII_KEYWORDS):
        tags.append("QDII")
    if any(keyword in name for keyword in THEME_KEYWORDS):
        tags.append("行业主题")
    if any(keyword in name for keyword in PENSION_KEYWORDS):
        tags.append("养老FOF")
    if any(keyword in name for keyword in BROAD_KEYWORDS):
        tags.append("核心宽基")
    if not tags:
        tags.append("待分类")
    for tag in extra_tags or []:
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _estimate_daily_profit(amount: float | None, daily_return: float | None) -> float | None:
    if amount is None or daily_return is None:
        return None
    rate = daily_return / 100
    if rate <= -0.999999:
        return None
    return round(float(amount) * rate / (1 + rate), 2)


def _normalize_quote_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "nat"}:
        return None
    return text[:10]


def _snapshot_date_from_source(source: str | None) -> str | None:
    if not source:
        return None
    if source.startswith("screenshot_"):
        raw = source.removeprefix("screenshot_").replace("_", "-")
        return raw if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) else None
    return None


async def enrich_latest_quotes(items: list[PortfolioItem]) -> dict[int, dict[str, Any]]:
    if os.getenv("STARMAP_ENABLE_PORTFOLIO_LIVE_QUOTES", "").lower() not in {"1", "true", "yes"}:
        return {
            item.id: {
                "code": item.fund_code,
                "source": "snapshot",
                "warning": "已使用截图/手工导入的持仓快照；实时净值刷新已暂时关闭，避免 AKShare 原生组件导致后端进程崩溃。",
                "snapshot_daily_profit": item.yesterday_profit,
                "snapshot_date": _snapshot_date_from_source(item.source),
            }
            for item in items
            if item.is_holding
        }
    holdings = [item for item in items if item.is_holding and item.fund_code]
    semaphore = asyncio.Semaphore(5)

    async def load(item: PortfolioItem) -> tuple[int, dict[str, Any]]:
        async with semaphore:
            try:
                quote = await get_latest_fund_quote(item.fund_code)
            except Exception as exc:
                quote = {"code": item.fund_code, "source": "error", "error": str(exc)}
            daily_return = quote.get("daily_return")
            quote["estimated_daily_profit"] = _estimate_daily_profit(item.amount, daily_return)
            return item.id, quote

    pairs = await asyncio.gather(*(load(item) for item in holdings))
    return dict(pairs)


def serialize_item(item: PortfolioItem, quote: dict[str, Any] | None = None) -> dict[str, Any]:
    quote = quote or {}
    return {
        "id": item.id,
        "fund_code": item.fund_code,
        "fund_name": item.fund_name,
        "source": item.source,
        "amount": item.amount,
        "yesterday_profit": item.yesterday_profit,
        "holding_profit": item.holding_profit,
        "holding_return_pct": item.holding_return_pct,
        "latest_nav": quote.get("latest_nav"),
        "previous_nav": quote.get("previous_nav"),
        "nav_date": quote.get("nav_date"),
        "nav_daily_return": quote.get("daily_return"),
        "estimated_daily_profit": quote.get("estimated_daily_profit"),
        "snapshot_daily_profit": quote.get("snapshot_daily_profit"),
        "snapshot_date": quote.get("snapshot_date") or _snapshot_date_from_source(item.source),
        "quote_source": quote.get("source"),
        "quote_warning": quote.get("warning"),
        "tags": item.tags or [],
        "confidence": item.confidence,
        "is_holding": item.is_holding,
        "is_watchlist": item.is_watchlist,
        "notes": item.notes,
        "created_at": str(item.created_at),
        "updated_at": str(item.updated_at),
    }


def serialize_action(action: PortfolioAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "item_id": action.item_id,
        "fund_code": action.fund_code,
        "fund_name": action.fund_name,
        "action_type": action.action_type,
        "amount": action.amount,
        "target_fund_code": action.target_fund_code,
        "target_fund_name": action.target_fund_name,
        "schedule": action.schedule,
        "status": action.status,
        "reason": action.reason,
        "metadata": action.metadata_json or {},
        "created_at": str(action.created_at),
        "updated_at": str(action.updated_at),
    }


def serialize_import(record: PortfolioImport) -> dict[str, Any]:
    return {
        "id": record.id,
        "filename": record.filename,
        "source_type": record.source_type,
        "status": record.status,
        "extracted_text": record.extracted_text,
        "parsed_items": record.parsed_items or [],
        "message": record.message,
        "created_at": str(record.created_at),
    }


def serialize_preference(pref: InvestmentPreference) -> dict[str, Any]:
    return {
        "id": pref.id,
        "risk_profile": pref.risk_profile,
        "strategy_goal": pref.strategy_goal,
        "max_single_fund_pct": pref.max_single_fund_pct,
        "max_qdii_pct": pref.max_qdii_pct,
        "allow_sector_funds": pref.allow_sector_funds,
        "max_drawdown_pct": pref.max_drawdown_pct,
        "max_theme_pct": pref.max_theme_pct,
        "min_cash_pct": pref.min_cash_pct,
        "rebalance_frequency": pref.rebalance_frequency,
        "notes": pref.notes,
        "updated_at": str(pref.updated_at),
    }


async def get_or_create_preference(db: AsyncSession) -> InvestmentPreference:
    result = await db.execute(select(InvestmentPreference).order_by(InvestmentPreference.id.asc()).limit(1))
    pref = result.scalar_one_or_none()
    if pref:
        return pref

    default = RISK_PROFILE_PRESETS["balanced"]
    pref = InvestmentPreference(
        risk_profile="balanced",
        strategy_goal="balanced_growth",
        max_single_fund_pct=default["max_single_fund_pct"],
        max_qdii_pct=default["max_qdii_pct"],
        allow_sector_funds=default["allow_sector_funds"],
        max_drawdown_pct=default["max_drawdown_pct"],
        max_theme_pct=default["max_theme_pct"],
        min_cash_pct=default["min_cash_pct"],
        rebalance_frequency=default["rebalance_frequency"],
    )
    db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return pref


async def upsert_seed_item(db: AsyncSession, payload: dict[str, Any], is_holding: bool) -> bool:
    fund_code = payload.get("fund_code", "").strip()
    fund_name = payload["fund_name"].strip()
    if not fund_code:
        match = await resolve_fund_code_by_name(fund_name)
        if match and match["score"] >= 78:
            fund_code = match["code"]
            payload = {**payload, "fund_code": fund_code, "confidence": "auto_resolved_by_name"}
    if fund_code:
        stmt = select(PortfolioItem).where(PortfolioItem.fund_code == fund_code)
    else:
        stmt = select(PortfolioItem).where(PortfolioItem.fund_code == "", PortfolioItem.fund_name == fund_name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    tags = classify_fund(fund_name, payload.get("tags"))

    if existing:
        existing.fund_name = fund_name
        existing.source = "screenshot_2026_05_14"
        existing.tags = tags
        existing.confidence = payload.get("confidence", "code_from_screenshot")
        existing.is_holding = existing.is_holding or is_holding
        existing.is_watchlist = True
        if is_holding:
            existing.amount = payload.get("amount", existing.amount)
            existing.yesterday_profit = payload.get("yesterday_profit")
            existing.holding_profit = payload.get("holding_profit")
            existing.holding_return_pct = payload.get("holding_return_pct")
        return False

    db.add(
        PortfolioItem(
            fund_code=fund_code,
            fund_name=fund_name,
            source="screenshot_2026_05_14",
            amount=payload.get("amount", 0.0),
            yesterday_profit=payload.get("yesterday_profit"),
            holding_profit=payload.get("holding_profit"),
            holding_return_pct=payload.get("holding_return_pct"),
            tags=tags,
            confidence=payload.get("confidence", "code_from_screenshot"),
            is_holding=is_holding,
            is_watchlist=True,
            notes="来自用户 2026-05-14 持仓/自选截图",
        )
    )
    return True


def normalize_fund_name(name: str) -> str:
    text = re.sub(r"[\s（）()\-_/·]", "", name.upper())
    for suffix in ("人民币份额", "人民币", "美元现汇", "美元现钞", "基金", "联接", "LOF", "ETF"):
        text = text.replace(suffix.upper(), "")
    text = re.sub(r"[ABC]$", "", text)
    return text


def score_fund_match(query: str, candidate: str) -> int:
    q = normalize_fund_name(query)
    c = normalize_fund_name(candidate)
    if not q or not c:
        return 0
    if q == c:
        return 100
    if q in c or c in q:
        return 92
    common = sum(1 for char in set(q) if char in c)
    return round(common / max(len(set(q)), 1) * 82)


async def resolve_fund_code_by_name(name: str) -> dict[str, Any] | None:
    override = KNOWN_FUND_CODE_OVERRIDES.get(name)
    if override:
        return {**override, "score": 100, "source": "verified_override"}

    catalog = await get_fund_catalog()
    candidates = [row for row in catalog if name in row["name"] or row["name"] in name]
    if not candidates:
        compact = re.sub(r"[AC]$|[（(].*?[）)]", "", name).strip()
        candidates = [row for row in catalog if compact and (compact in row["name"] or row["name"] in compact)]
    if not candidates:
        query_chars = set(normalize_fund_name(name))
        candidates = [
            row for row in catalog
            if len(query_chars.intersection(set(row["normalized_name"]))) >= max(4, min(8, len(query_chars) // 2))
        ][:80]
    best: dict[str, Any] | None = None
    for candidate in candidates:
        code = str(candidate.get("code", "")).strip()
        candidate_name = str(candidate.get("name", "")).strip()
        if not code or not candidate_name:
            continue
        score = score_fund_match(name, candidate_name)
        row = {
            "code": code,
            "name": candidate_name,
            "fund_type": candidate.get("fund_type", ""),
            "score": score,
            "source": candidate.get("source", "akshare_fund_name_em"),
        }
        if best is None or row["score"] > best["score"]:
            best = row
    return best


async def get_fund_catalog() -> list[dict[str, Any]]:
    now = time.time()
    cached = FUND_CATALOG_CACHE.get("items") or []
    if cached and now < float(FUND_CATALOG_CACHE.get("expires_at", 0)):
        return cached

    df = await asyncio.to_thread(ak.fund_name_em)
    items: list[dict[str, Any]] = []
    for _, record in df.iterrows():
        row = record.to_dict()
        code = str(row.get("基金代码", "")).strip()
        name = str(row.get("基金简称", "")).strip()
        if not code or not name:
            continue
        items.append(
            {
                "code": code,
                "name": name,
                "fund_type": str(row.get("基金类型", "")).strip(),
                "normalized_name": normalize_fund_name(name),
                "source": "akshare_fund_name_em",
            }
        )
    FUND_CATALOG_CACHE["items"] = items
    FUND_CATALOG_CACHE["expires_at"] = now + 24 * 3600
    return items


async def extract_text_from_image(path: Path) -> tuple[str, str]:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        text = pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng")
        return text.strip(), "pytesseract"
    except Exception:
        return "", "none"


def parse_portfolio_text(text: str, source_type: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items: list[dict[str, Any]] = []
    used_names: set[str] = set()
    code_pattern = re.compile(r"\b(\d{6})\b")
    amount_pattern = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+\.\d{1,2})(?!\d)")

    for index, line in enumerate(lines):
        code_match = code_pattern.search(line)
        if not code_match:
            continue
        code = code_match.group(1)
        neighbors = lines[max(0, index - 2): index + 2]
        name_parts = [part for part in neighbors if code not in part and not amount_pattern.fullmatch(part)]
        fund_name = max(name_parts, key=len, default="").strip()
        if not fund_name:
            continue
        amount = None
        for neighbor in neighbors:
            numbers = amount_pattern.findall(neighbor.replace("，", ","))
            if numbers:
                try:
                    amount = float(numbers[-1].replace(",", ""))
                except ValueError:
                    amount = None
        key = f"{code}:{fund_name}"
        if key in used_names:
            continue
        used_names.add(key)
        items.append(
            {
                "fund_code": code,
                "fund_name": fund_name[:160],
                "amount": amount or 0.0,
                "source": "image_ocr",
                "confidence": "ocr_code",
                "is_holding": source_type == "holding",
                "is_watchlist": True,
            }
        )
    return items


async def upsert_imported_items(db: AsyncSession, items: list[dict[str, Any]]) -> dict[str, int]:
    created = 0
    updated = 0
    for payload in items:
        if await upsert_seed_item(db, payload, is_holding=bool(payload.get("is_holding"))):
            created += 1
        else:
            updated += 1
    await db.commit()
    return {"created": created, "updated": updated}


def build_exposure(items: list[PortfolioItem], pref: InvestmentPreference, quotes: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    quotes = quotes or {}
    holdings = [item for item in items if item.is_holding]
    total_amount = round(sum(item.amount or 0 for item in holdings), 2)
    daily_profit_values = [
        quote.get("estimated_daily_profit")
        for quote in (quotes.get(item.id, {}) for item in holdings)
        if quote.get("estimated_daily_profit") is not None
    ]
    snapshot_profit_values = [
        quote.get("snapshot_daily_profit")
        for quote in (quotes.get(item.id, {}) for item in holdings)
        if quote.get("snapshot_daily_profit") is not None
    ]
    snapshot_dates = [
        snapshot_date
        for snapshot_date in (quotes.get(item.id, {}).get("snapshot_date") or _snapshot_date_from_source(item.source) for item in holdings)
        if snapshot_date
    ]
    quote_dates = [
        quote_date
        for quote_date in (_normalize_quote_date(quotes.get(item.id, {}).get("nav_date")) for item in holdings)
        if quote_date
    ]
    quote_date_counts: dict[str, int] = {}
    for quote_date in quote_dates:
        quote_date_counts[quote_date] = quote_date_counts.get(quote_date, 0) + 1
    latest_quote_date = max(quote_dates) if quote_dates else None
    oldest_quote_date = min(quote_dates) if quote_dates else None
    today = date.today().isoformat()
    estimated_daily_profit = round(sum(float(value) for value in daily_profit_values), 2) if daily_profit_values else None
    previous_total_amount = total_amount - estimated_daily_profit if estimated_daily_profit is not None else None
    snapshot_daily_profit = round(sum(float(value) for value in snapshot_profit_values), 2) if snapshot_profit_values else None
    snapshot_previous_amount = total_amount - snapshot_daily_profit if snapshot_daily_profit is not None else None
    positions: list[dict[str, Any]] = []
    qdii_amount = 0.0
    theme_amount = 0.0
    pension_amount = 0.0

    for item in holdings:
        amount = item.amount or 0.0
        tags = classify_fund(item.fund_name, item.tags or [])
        pct = amount / total_amount * 100 if total_amount else 0.0
        if "QDII" in tags:
            qdii_amount += amount
        if "行业主题" in tags:
            theme_amount += amount
        if "养老FOF" in tags:
            pension_amount += amount
        positions.append(
            {
                "id": item.id,
                "fund_code": item.fund_code,
                "fund_name": item.fund_name,
                "amount": round(amount, 2),
                "position_pct": round(pct, 2),
                "holding_return_pct": item.holding_return_pct,
                "nav_daily_return": quotes.get(item.id, {}).get("daily_return"),
                "estimated_daily_profit": quotes.get(item.id, {}).get("estimated_daily_profit"),
                "snapshot_daily_profit": quotes.get(item.id, {}).get("snapshot_daily_profit"),
                "snapshot_date": quotes.get(item.id, {}).get("snapshot_date") or _snapshot_date_from_source(item.source),
                "tags": tags,
            }
        )

    positions.sort(key=lambda row: row["position_pct"], reverse=True)
    largest = positions[0] if positions else None

    return {
        "total_amount": total_amount,
        "estimated_daily_profit": estimated_daily_profit,
        "estimated_daily_return_pct": round(estimated_daily_profit / previous_total_amount * 100, 4)
        if estimated_daily_profit is not None and previous_total_amount else None,
        "snapshot_daily_profit": snapshot_daily_profit,
        "snapshot_daily_return_pct": round(snapshot_daily_profit / snapshot_previous_amount * 100, 4)
        if snapshot_daily_profit is not None and snapshot_previous_amount else None,
        "snapshot_covered_count": len(snapshot_profit_values),
        "snapshot_date": max(snapshot_dates) if snapshot_dates else None,
        "quote_covered_count": len(daily_profit_values),
        "quote_latest_date": latest_quote_date,
        "quote_oldest_date": oldest_quote_date,
        "quote_date_counts": quote_date_counts,
        "quote_today": today,
        "quote_is_today": latest_quote_date == today,
        "holding_count": len(holdings),
        "watchlist_count": len([item for item in items if item.is_watchlist and not item.is_holding]),
        "qdii_amount": round(qdii_amount, 2),
        "qdii_pct": round(qdii_amount / total_amount * 100, 2) if total_amount else 0.0,
        "theme_amount": round(theme_amount, 2),
        "theme_pct": round(theme_amount / total_amount * 100, 2) if total_amount else 0.0,
        "pension_amount": round(pension_amount, 2),
        "pension_pct": round(pension_amount / total_amount * 100, 2) if total_amount else 0.0,
        "largest_position": largest,
        "top_positions": positions[:8],
        "constraints": {
            "max_single_fund_pct": pref.max_single_fund_pct,
            "max_qdii_pct": pref.max_qdii_pct,
            "max_theme_pct": pref.max_theme_pct,
            "max_drawdown_pct": pref.max_drawdown_pct,
            "min_cash_pct": pref.min_cash_pct,
            "allow_sector_funds": pref.allow_sector_funds,
        },
    }


def build_alerts(exposure: dict[str, Any], pref: InvestmentPreference) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    largest = exposure.get("largest_position")
    if largest and largest["position_pct"] > pref.max_single_fund_pct:
        alerts.append(
            {
                "level": "high",
                "title": "单只基金仓位过高",
                "detail": f"{largest['fund_name']} 占比 {largest['position_pct']:.2f}%，高于上限 {pref.max_single_fund_pct:.2f}%。",
                "action": "后续新增资金优先避开该基金；需要降集中度时先做减仓候选。",
            }
        )
    if exposure["qdii_pct"] > pref.max_qdii_pct:
        alerts.append(
            {
                "level": "medium",
                "title": "QDII 仓位超出偏好",
                "detail": f"当前 QDII 占比 {exposure['qdii_pct']:.2f}%，高于上限 {pref.max_qdii_pct:.2f}%。",
                "action": "新买入先放回国内宽基、债基或现金仓；QDII 只做观察和再平衡。",
            }
        )
    if not pref.allow_sector_funds and exposure["theme_pct"] > 0:
        alerts.append(
            {
                "level": "high",
                "title": "当前组合含行业主题基金",
                "detail": f"你当前设置不允许行业主题基金，但组合主题占比 {exposure['theme_pct']:.2f}%。",
                "action": "可以先设置过渡上限，再分批切回宽基/FOF/低波资产。",
            }
        )
    elif exposure["theme_pct"] > pref.max_theme_pct:
        alerts.append(
            {
                "level": "medium",
                "title": "行业主题基金占比偏高",
                "detail": f"当前主题占比 {exposure['theme_pct']:.2f}%，高于上限 {pref.max_theme_pct:.2f}%。",
                "action": "科技、新能源、半导体等同类赛道需要合并看仓位，避免重复暴露。",
            }
        )
    for position in exposure["top_positions"]:
        return_pct = position.get("holding_return_pct")
        if return_pct is not None and return_pct < -pref.max_drawdown_pct:
            alerts.append(
                {
                    "level": "high",
                    "title": "持仓亏损接近回撤阈值",
                    "detail": f"{position['fund_name']} 当前持有收益率 {return_pct:.2f}%，低于 -{pref.max_drawdown_pct:.2f}%。",
                    "action": "先复盘基本面和买入理由，再决定止损、降仓或继续定投。",
                }
            )
    if pref.min_cash_pct > 0:
        alerts.append(
            {
                "level": "info",
                "title": "现金仓需要单独录入",
                "detail": f"偏好要求至少 {pref.min_cash_pct:.2f}% 现金/低波仓位，目前截图未包含现金或货币基金。",
                "action": "后续可把货币基金、短债或现金作为组合条目录入，策略会自动纳入约束。",
            }
        )
    return alerts


def build_current_strategy(exposure: dict[str, Any], pref: InvestmentPreference) -> dict[str, Any]:
    goal = GOAL_OPTIONS[pref.strategy_goal]
    profile = RISK_PROFILE_PRESETS.get(pref.risk_profile, {"label": "自定义", "description": "使用自定义仓位约束。"})
    actions: list[str] = []

    if pref.risk_profile == "conservative":
        actions.extend(
            [
                "优先把新增资金放到现金、短债、低波宽基或养老FOF，主题基金只做小仓观察。",
                "科技、新能源、半导体等成长赛道当前相关性较高，按同一风险桶合并控制。",
                "净值新高后不追高加仓，等回撤或月度再平衡窗口处理。",
            ]
        )
    elif pref.risk_profile == "aggressive":
        actions.extend(
            [
                "可保留主题进攻性，但每个主题都要有上限、止损线和复盘触发条件。",
                "新增主题仓采用分批买入，避免一次性把波动暴露打满。",
                "若 QDII 或主题仓接近上限，后续候选只能用于替换，不能继续叠加。",
            ]
        )
    else:
        actions.extend(
            [
                "采用核心-卫星结构：核心仓负责稳定，主题和 QDII 负责增强。",
                "单只基金超过上限后，新增资金优先补低占比核心仓。",
                "每月用同一套偏好约束复盘，避免因为短期涨跌频繁改变规则。",
            ]
        )

    if exposure["theme_pct"] > pref.max_theme_pct:
        actions.insert(0, "当前主题仓高于偏好上限，下一步先停止新增同类赛道。")
    if exposure["qdii_pct"] > pref.max_qdii_pct:
        actions.insert(0, "当前 QDII 仓位高于偏好上限，海外基金先暂停加仓。")

    return {
        "profile_label": profile["label"],
        "profile_description": profile["description"],
        "goal_label": goal["label"],
        "target_allocation": goal["target_allocation"],
        "rules": goal["rules"],
        "actions": actions,
    }


def build_action_suggestions(item: PortfolioItem, exposure: dict[str, Any], pref: InvestmentPreference) -> list[dict[str, Any]]:
    tags = classify_fund(item.fund_name, item.tags or [])
    amount = item.amount or 0.0
    total = exposure["total_amount"] or 0.0
    position_pct = amount / total * 100 if total else 0.0
    suggestions: list[dict[str, Any]] = [
        {
            "action_type": "analyze",
            "label": "分析",
            "priority": "normal",
            "reason": "查看净值、回撤、持仓和同类排名后再决定交易。",
        }
    ]
    if item.is_holding:
        if position_pct > pref.max_single_fund_pct:
            suggestions.append(
                {
                    "action_type": "sell",
                    "label": "减仓",
                    "priority": "high",
                    "reason": f"当前占比 {position_pct:.2f}%，高于单只上限 {pref.max_single_fund_pct:.2f}%。",
                }
            )
            suggestions.append(
                {
                    "action_type": "switch",
                    "label": "转换",
                    "priority": "normal",
                    "reason": "可考虑把超额部分转换到低相关的宽基、债基或现金类资产。",
                }
            )
        elif "行业主题" in tags and exposure["theme_pct"] > pref.max_theme_pct:
            suggestions.append(
                {
                    "action_type": "pause_auto_invest",
                    "label": "暂停定投",
                    "priority": "high",
                    "reason": f"主题基金总仓位 {exposure['theme_pct']:.2f}%，已经高于你的上限。",
                }
            )
        elif (item.holding_return_pct or 0) < -pref.max_drawdown_pct:
            suggestions.append(
                {
                    "action_type": "sell",
                    "label": "止损复核",
                    "priority": "high",
                    "reason": "持有收益率已低于你的最大可接受回撤，先复盘买入逻辑。",
                }
            )
        else:
            suggestions.append(
                {
                    "action_type": "auto_invest",
                    "label": "定投",
                    "priority": "normal",
                    "reason": "仓位未触发硬性风险阈值，可用小额定投替代一次性买入。",
                }
            )
            suggestions.append(
                {
                    "action_type": "buy",
                    "label": "加仓",
                    "priority": "low",
                    "reason": "仅在估值、趋势和组合仓位都通过时考虑分批加仓。",
                }
            )
    else:
        suggestions.append(
            {
                "action_type": "auto_invest",
                "label": "加入定投观察",
                "priority": "normal",
                "reason": "先用观察仓或模拟定投跟踪，不急于一次性买入。",
            }
        )
    return suggestions


@router.get("/preferences", summary="获取投资偏好")
async def get_preferences(db: AsyncSession = Depends(get_db)):
    pref = await get_or_create_preference(db)
    return {
        "preference": serialize_preference(pref),
        "presets": RISK_PROFILE_PRESETS,
        "goal_options": GOAL_OPTIONS,
    }


@router.put("/preferences", summary="保存投资偏好")
async def update_preferences(req: PreferencePatchRequest, db: AsyncSession = Depends(get_db)):
    pref = await get_or_create_preference(db)
    data = req.model_dump(exclude_unset=True)

    risk_profile = data.get("risk_profile")
    if risk_profile is not None and risk_profile not in {"conservative", "balanced", "aggressive", "custom"}:
        raise HTTPException(status_code=422, detail="risk_profile 仅支持 conservative/balanced/aggressive/custom")
    if data.get("strategy_goal") is not None and data["strategy_goal"] not in GOAL_OPTIONS:
        raise HTTPException(status_code=422, detail="未知策略目标")

    if data.get("apply_profile_defaults") and risk_profile in RISK_PROFILE_PRESETS:
        preset = RISK_PROFILE_PRESETS[risk_profile]
        for field in (
            "max_single_fund_pct",
            "max_qdii_pct",
            "allow_sector_funds",
            "max_drawdown_pct",
            "max_theme_pct",
            "min_cash_pct",
            "rebalance_frequency",
        ):
            setattr(pref, field, preset[field])

    for field, value in data.items():
        if field == "apply_profile_defaults" or value is None:
            continue
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    return {"message": "保存成功", "preference": serialize_preference(pref)}


@router.get("/items", summary="获取组合条目")
async def get_portfolio_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioItem).order_by(PortfolioItem.is_holding.desc(), PortfolioItem.amount.desc()))
    items = result.scalars().all()
    quotes = await enrich_latest_quotes(items)
    return {"count": len(items), "items": [serialize_item(item, quotes.get(item.id)) for item in items]}


@router.post("/items/resolve-codes", summary="按基金名称自动补齐代码")
async def resolve_missing_codes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioItem).where(PortfolioItem.fund_code == ""))
    items = result.scalars().all()
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for item in items:
        match = await resolve_fund_code_by_name(item.fund_name)
        if match and match["score"] >= 78:
            item.fund_code = match["code"]
            item.confidence = "auto_resolved_by_name"
            resolved.append({"id": item.id, "fund_name": item.fund_name, "match": match})
        else:
            unresolved.append({"id": item.id, "fund_name": item.fund_name, "best_match": match})

    await db.commit()
    return {
        "message": "代码补齐完成",
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "resolved": resolved,
        "unresolved": unresolved,
    }


@router.post("/items", summary="新增组合条目")
async def create_portfolio_item(req: PortfolioItemRequest, db: AsyncSession = Depends(get_db)):
    fund_code = req.fund_code
    confidence = "manual"
    if not fund_code:
        match = await resolve_fund_code_by_name(req.fund_name)
        if match and match["score"] >= 78:
            fund_code = match["code"]
            confidence = "auto_resolved_by_name"
    item = PortfolioItem(
        fund_code=fund_code,
        fund_name=req.fund_name.strip(),
        source=req.source,
        amount=req.amount,
        yesterday_profit=req.yesterday_profit,
        holding_profit=req.holding_profit,
        holding_return_pct=req.holding_return_pct,
        tags=classify_fund(req.fund_name, req.tags),
        confidence=confidence,
        is_holding=req.is_holding,
        is_watchlist=req.is_watchlist,
        notes=req.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    quotes = await enrich_latest_quotes([item])
    return {"message": "保存成功", "item": serialize_item(item, quotes.get(item.id))}


@router.delete("/items/{item_id}", summary="删除组合条目")
async def delete_portfolio_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(PortfolioItem).where(PortfolioItem.id == item_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="未找到组合条目")
    await db.commit()
    return {"message": "删除成功", "id": item_id}


@router.post("/items/seed", summary="导入截图持仓和自选")
async def seed_portfolio_items(db: AsyncSession = Depends(get_db)):
    created = 0
    updated = 0
    for payload in SCREENSHOT_HOLDINGS:
        if await upsert_seed_item(db, payload, is_holding=True):
            created += 1
        else:
            updated += 1
    for payload in SCREENSHOT_WATCHLIST:
        if await upsert_seed_item(db, payload, is_holding=False):
            created += 1
        else:
            updated += 1
    await db.commit()
    return {
        "message": "截图清单已导入",
        "created": created,
        "updated": updated,
        "holding_seed_count": len(SCREENSHOT_HOLDINGS),
        "watchlist_seed_count": len(SCREENSHOT_WATCHLIST),
        "note": "已尝试按基金名称自动补齐代码；仍未匹配的条目会保留名称和金额。",
    }


@router.post("/import-image", summary="上传截图/照片导入持仓")
async def import_portfolio_image(
    file: UploadFile = File(...),
    source_type: str = Form(default="holding"),
    ocr_text: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    if source_type not in {"holding", "watchlist"}:
        raise HTTPException(status_code=422, detail="source_type 仅支持 holding/watchlist")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        raise HTTPException(status_code=422, detail="仅支持 jpg/jpeg/png/webp/bmp 图片")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{suffix}"
    saved_path = UPLOAD_DIR / saved_name
    with saved_path.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    extracted_text = ocr_text.strip()
    ocr_provider = "provided_text" if extracted_text else "none"
    if not extracted_text:
        extracted_text, ocr_provider = await extract_text_from_image(saved_path)

    parsed_items = parse_portfolio_text(extracted_text, source_type) if extracted_text else []
    counts = await upsert_imported_items(db, parsed_items) if parsed_items else {"created": 0, "updated": 0}
    status = "imported" if parsed_items else "uploaded"
    message = (
        f"已解析并导入 {len(parsed_items)} 条。"
        if parsed_items
        else "图片已保存；当前环境没有可用 OCR 或识别结果不足，可稍后补充 OCR 文本或接入 Qwen-VL/本地 OCR。"
    )
    record = PortfolioImport(
        filename=file.filename or saved_name,
        saved_path=str(saved_path),
        source_type=source_type,
        status=status,
        extracted_text=extracted_text,
        parsed_items=parsed_items,
        message=f"{message} OCR: {ocr_provider}",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {**serialize_import(record), **counts}


@router.post("/import-text", summary="从截图 OCR 文本导入持仓")
async def import_portfolio_text(req: ImportTextRequest, db: AsyncSession = Depends(get_db)):
    parsed_items = parse_portfolio_text(req.text, req.source_type)
    counts = await upsert_imported_items(db, parsed_items) if parsed_items else {"created": 0, "updated": 0}
    return {
        "message": f"已解析 {len(parsed_items)} 条",
        "parsed_items": parsed_items,
        **counts,
    }


@router.get("/imports", summary="获取上传导入记录")
async def get_import_records(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioImport).order_by(PortfolioImport.created_at.desc()).limit(30))
    records = result.scalars().all()
    return {"count": len(records), "items": [serialize_import(record) for record in records]}


@router.get("/items/{item_id}/actions", summary="获取基金操作记录")
async def get_item_actions(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioAction).where(PortfolioAction.item_id == item_id).order_by(PortfolioAction.created_at.desc()))
    actions = result.scalars().all()
    return {"count": len(actions), "items": [serialize_action(action) for action in actions]}


@router.post("/items/{item_id}/actions", summary="记录基金操作计划")
async def create_item_action(item_id: int, req: PortfolioActionRequest, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(PortfolioItem).where(PortfolioItem.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="未找到组合条目")
    action = PortfolioAction(
        item_id=item.id,
        fund_code=item.fund_code,
        fund_name=item.fund_name,
        action_type=req.action_type,
        amount=req.amount,
        target_fund_code=req.target_fund_code,
        target_fund_name=req.target_fund_name,
        schedule=req.schedule,
        status=req.status,
        reason=req.reason,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return {"message": "操作已记录", "action": serialize_action(action)}


@router.get("/items/{item_id}/action-suggestions", summary="获取基金操作建议")
async def get_item_action_suggestions(item_id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(PortfolioItem).where(PortfolioItem.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="未找到组合条目")
    pref = await get_or_create_preference(db)
    result = await db.execute(select(PortfolioItem))
    items = result.scalars().all()
    quotes = await enrich_latest_quotes(items)
    exposure = build_exposure(items, pref, quotes)
    return {
        "item": serialize_item(item, quotes.get(item.id)),
        "suggestions": build_action_suggestions(item, exposure, pref),
    }


@router.get("/strategy", summary="生成组合策略建议")
async def get_portfolio_strategy(db: AsyncSession = Depends(get_db)):
    pref = await get_or_create_preference(db)
    result = await db.execute(select(PortfolioItem))
    items = result.scalars().all()
    quotes = await enrich_latest_quotes(items)
    exposure = build_exposure(items, pref, quotes)
    alerts = build_alerts(exposure, pref)
    strategy = build_current_strategy(exposure, pref)
    return {
        "preference": serialize_preference(pref),
        "exposure": exposure,
        "alerts": alerts,
        "current_strategy": strategy,
        "strategy_options": GOAL_OPTIONS,
        "disclaimer": "仅用于个人投研辅助，最终交易仍需人工确认。",
    }
