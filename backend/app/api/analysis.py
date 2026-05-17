"""分析历史 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import Analysis


router = APIRouter(prefix="/api/analysis", tags=["分析历史"])


class CreateAnalysisRequest(BaseModel):
    title: str
    query: str
    response: str
    skills_used: list[str] = []
    fund_codes: list[str] = []


@router.get("/history", summary="获取分析历史")
async def get_analysis_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Analysis).order_by(Analysis.created_at.desc()).limit(100))
    items = result.scalars().all()
    return {
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "query": item.query,
                "response": item.response,
                "skills_used": item.skills_used,
                "fund_codes": item.fund_codes,
                "created_at": str(item.created_at),
            }
            for item in items
        ],
    }


@router.post("/history", summary="保存分析记录")
async def create_analysis(req: CreateAnalysisRequest, db: AsyncSession = Depends(get_db)):
    item = Analysis(
        title=req.title,
        query=req.query,
        response=req.response,
        skills_used=req.skills_used,
        fund_codes=req.fund_codes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "message": "保存成功"}
