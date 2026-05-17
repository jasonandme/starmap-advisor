"""系统自查 API。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.agent.llm_factory import get_llm
from app.config import get_settings
from app.data.akshare_fund import get_fund_rank
from app.database import async_session
from app.skills.registry import skill_registry


router = APIRouter(prefix="/api/system", tags=["系统"])


def _mask_configured(value: str) -> bool:
    return bool(value and not value.startswith("sk-your") and "your-" not in value)


def _llm_options(settings):
    return [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "model": settings.DEEPSEEK_MODEL,
            "reasoner_model": settings.DEEPSEEK_REASONER_MODEL,
            "configured": _mask_configured(settings.DEEPSEEK_API_KEY),
        },
        {
            "id": "kimi",
            "name": "Kimi",
            "model": settings.KIMI_MODEL,
            "reasoner_model": settings.KIMI_MODEL,
            "configured": _mask_configured(settings.KIMI_API_KEY),
        },
        {
            "id": "qwen",
            "name": "通义千问",
            "model": settings.QWEN_MODEL,
            "reasoner_model": settings.QWEN_MODEL,
            "configured": _mask_configured(settings.QWEN_API_KEY),
        },
    ]


def _check_result(
    name: str,
    status: str,
    detail: str,
    extra: dict[str, Any] | None = None,
):
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "extra": extra or {},
    }


@router.get("/llm-options", summary="模型选择")
async def llm_options():
    settings = get_settings()
    return {
        "active": settings.ACTIVE_LLM,
        "options": _llm_options(settings),
    }


@router.get("/self-check", summary="系统自查")
async def self_check():
    """检查运行环境、数据源、数据库、skill 和 LLM 连通性。"""
    settings = get_settings()
    checks: list[dict[str, Any]] = []

    options = _llm_options(settings)
    active_option = next((item for item in options if item["id"] == settings.ACTIVE_LLM), options[0])
    key_loaded = bool(active_option["configured"])
    checks.append(
        _check_result(
            "config",
            "ok" if key_loaded else "warn",
            f"{active_option['name']} key 已加载" if key_loaded else f"{active_option['name']} key 未配置，将使用本地模板解释",
            {
                "active_llm": settings.ACTIVE_LLM,
                "llm_options": options,
                "database": settings.DATABASE_URL.split("///")[-1],
                "redis_url_present": bool(settings.REDIS_URL),
            },
        )
    )

    try:
        async with async_session() as session:
            await session.execute(text("select 1"))
        checks.append(_check_result("database", "ok", "数据库连接正常"))
    except Exception as exc:
        checks.append(_check_result("database", "fail", str(exc)))

    skill_names = skill_registry.names
    expected = {
        "fund_search",
        "fund_rank",
        "fund_detail",
        "fund_compare",
        "fund_holding",
        "fund_recommend",
        "stock_quote",
        "news_fetch",
    }
    missing = sorted(expected.difference(skill_names))
    checks.append(
        _check_result(
            "skills",
            "ok" if not missing else "fail",
            "核心 skill 已注册" if not missing else f"缺少 skill: {', '.join(missing)}",
            {"count": len(skill_names), "names": skill_names},
        )
    )

    try:
        data = await asyncio.wait_for(get_fund_rank("QDII", 1), timeout=30)
        source = data.get("source", "unknown")
        checks.append(
            _check_result(
                "akshare",
                "ok" if data.get("funds") else "warn",
                f"基金数据源可用，来源：{source}" if data.get("funds") else "基金数据为空或使用降级数据",
                {"fund_count": len(data.get("funds", [])), "warning": data.get("warning")},
            )
        )
    except Exception as exc:
        checks.append(_check_result("akshare", "fail", str(exc)))

    if key_loaded:
        try:
            llm = get_llm(settings)
            response = await asyncio.wait_for(
                llm.ainvoke("\u53ea\u56de\u590d OK"),
                timeout=30,
            )
            content = str(getattr(response, "content", "")).strip()
            checks.append(
                _check_result(
                    "llm",
                    "ok" if "OK" in content.upper() else "warn",
                    f"{active_option['name']} API 连通" if content else f"{active_option['name']} API 有响应但内容为空",
                    {"model": active_option["model"]},
                )
            )
        except Exception as exc:
            checks.append(
                _check_result(
                    "llm",
                    "fail",
                    str(exc),
                    {"model": active_option["model"]},
                )
            )
    else:
        checks.append(_check_result("llm", "warn", "未配置 key，跳过 LLM 连通检查"))

    if any(item["status"] == "fail" for item in checks):
        overall = "fail"
    elif any(item["status"] == "warn" for item in checks):
        overall = "warn"
    else:
        overall = "ok"

    return {
        "status": overall,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "checks": checks,
    }
