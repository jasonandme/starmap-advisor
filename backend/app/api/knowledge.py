"""知识库 / RAG API。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import KnowledgeChunk
from app.rag.curated_sources import CURATED_KNOWLEDGE_SOURCES
from app.rag.service import ingest_knowledge_text, retrieve_knowledge


router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


class IngestTextRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source: str = "manual"
    category: str = "market_analysis"


class IngestUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    title: str | None = Field(default=None, max_length=200)
    category: str = "market_analysis"


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p>|</div>|</li>|</h[1-6]>", "\n", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


async def _fetch_url_text(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="仅支持 http/https 地址")
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "StarmapAdvisorKnowledgeBot/0.1"},
    ) as client:
        response = await client.get(url)
    response.raise_for_status()
    raw = response.text[:3_000_000]
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else url
    text = _html_to_text(raw)
    if len(text) < 80:
        raise HTTPException(status_code=422, detail="网页正文过短，未写入知识库")
    return title, text


@router.get("/sources", summary="查看推荐知识源")
async def curated_sources():
    return {"count": len(CURATED_KNOWLEDGE_SOURCES), "items": CURATED_KNOWLEDGE_SOURCES}


@router.post("/ingest-text", summary="写入知识文本")
async def ingest_text(req: IngestTextRequest, db: AsyncSession = Depends(get_db)):
    return await ingest_knowledge_text(
        db,
        text=req.content,
        title=req.title,
        source=req.source,
        category=req.category,
    )


@router.post("/ingest-url", summary="从网页写入知识库")
async def ingest_url(req: IngestUrlRequest, db: AsyncSession = Depends(get_db)):
    try:
        page_title, text = await _fetch_url_text(req.url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"网页读取失败：{exc}") from exc
    return await ingest_knowledge_text(
        db,
        text=text,
        title=req.title or page_title,
        source=f"url:{req.url}",
        category=req.category,
    )


@router.post("/ingest-file", summary="上传 txt/md 知识文件")
async def ingest_file(
    file: UploadFile = File(...),
    category: str = Form(default="market_analysis"),
    db: AsyncSession = Depends(get_db),
):
    filename = file.filename or "uploaded.txt"
    if not filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=422, detail="当前仅支持 .txt/.md 文件")
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")
    return await ingest_knowledge_text(
        db,
        text=text,
        title=filename,
        source=f"upload:{filename}",
        category=category,
    )


@router.get("/search", summary="检索知识库")
async def search_knowledge(
    q: str,
    top_k: int = 5,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items = await retrieve_knowledge(db, q, top_k=max(1, min(top_k, 20)), category=category)
    return {"count": len(items), "items": items}


@router.get("/chunks", summary="查看知识片段")
async def list_chunks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeChunk).order_by(KnowledgeChunk.created_at.desc()).limit(100))
    chunks = result.scalars().all()
    total = await db.scalar(select(func.count()).select_from(KnowledgeChunk))
    return {
        "count": len(chunks),
        "total": total or 0,
        "items": [
            {
                "id": chunk.id,
                "title": chunk.title,
                "source": chunk.source,
                "category": chunk.category,
                "preview": chunk.content[:220],
                "created_at": str(chunk.created_at),
            }
            for chunk in chunks
        ],
    }


@router.delete("/chunks/{chunk_id}", summary="删除知识片段")
async def delete_chunk(chunk_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="未找到知识片段")
    await db.commit()
    return {"message": "删除成功", "id": chunk_id}


@router.delete("/category/{category}", summary="按分类清理知识片段")
async def delete_category(category: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.category == category))
    await db.commit()
    return {"message": "删除成功", "category": category, "deleted": result.rowcount or 0}
