"""板块风向 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.akshare_sector import get_sector_news, get_sector_overview


router = APIRouter(prefix="/api/sectors", tags=["板块风向"])


@router.get("/overview")
async def sector_overview(
    limit: int = Query(80, ge=10, le=300),
    refresh: bool = Query(default=False, description="绕过本地缓存强制刷新"),
):
    try:
        return await get_sector_overview(limit=limit, force_refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"板块数据暂不可用：{exc}") from exc


@router.get("/{name}/news")
async def sector_news(
    name: str,
    limit: int = Query(10, ge=1, le=30),
    refresh: bool = Query(default=False, description="绕过本地缓存强制刷新"),
):
    try:
        return await get_sector_news(name=name, limit=limit, force_refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"板块资讯暂不可用：{exc}") from exc
