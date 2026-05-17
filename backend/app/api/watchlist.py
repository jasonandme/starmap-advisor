"""
星图智顾 - API 路由：自选基金
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database import get_db
from app.models.watchlist import Watchlist
from pydantic import BaseModel

router = APIRouter(prefix="/api/watchlist", tags=["自选"])


class AddWatchlistRequest(BaseModel):
    fund_code: str
    fund_name: str = ""
    note: str = ""


@router.get("", summary="获取自选列表")
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watchlist).order_by(Watchlist.added_at.desc()))
    items = result.scalars().all()
    return {
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "fund_code": item.fund_code,
                "fund_name": item.fund_name,
                "note": item.note,
                "added_at": str(item.added_at),
            }
            for item in items
        ],
    }


@router.post("", summary="添加自选")
async def add_to_watchlist(req: AddWatchlistRequest, db: AsyncSession = Depends(get_db)):
    # 检查是否已存在
    existing = await db.execute(
        select(Watchlist).where(Watchlist.fund_code == req.fund_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该基金已在自选中")

    item = Watchlist(
        fund_code=req.fund_code,
        fund_name=req.fund_name,
        note=req.note,
    )
    db.add(item)
    await db.commit()
    return {"message": "添加成功", "fund_code": req.fund_code}


@router.delete("/{fund_code}", summary="删除自选")
async def remove_from_watchlist(fund_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        delete(Watchlist).where(Watchlist.fund_code == fund_code)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="未找到该自选基金")
    await db.commit()
    return {"message": "删除成功", "fund_code": fund_code}
