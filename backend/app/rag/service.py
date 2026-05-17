"""轻量 RAG 服务：切片、入库、检索。

当前版本使用 SQLite 中的 KnowledgeChunk 表和本地词项重叠评分，先把 RAG 闭环跑通。
后续可把 embedding 字段迁移到 pgvector、Chroma、Qdrant 或 Qlib 离线特征库。
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk


CHUNK_SIZE = 900
CHUNK_OVERLAP = 140


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def tokenize(text: str) -> set[str]:
    text = normalize_text(text).lower()
    latin = set(re.findall(r"[a-z0-9]{2,}", text))
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    terms = set(latin)
    for block in chinese:
        if len(block) <= 2:
            terms.add(block)
            continue
        for size in (2, 3, 4):
            for index in range(0, len(block) - size + 1):
                terms.add(block[index:index + size])
    return {term for term in terms if term}


def score_chunk(query_terms: set[str], chunk_terms: set[str], content: str) -> float:
    if not query_terms or not chunk_terms:
        return 0.0
    overlap = query_terms.intersection(chunk_terms)
    if not overlap:
        return 0.0
    coverage = len(overlap) / max(len(query_terms), 1)
    density = len(overlap) / math.sqrt(max(len(chunk_terms), 1))
    exact_bonus = 0.2 if any(term in content.lower() for term in query_terms if len(term) >= 4) else 0.0
    return round(coverage * 0.7 + density * 0.3 + exact_bonus, 6)


async def ingest_knowledge_text(
    db: AsyncSession,
    *,
    text: str,
    title: str,
    source: str = "manual",
    category: str = "market_analysis",
) -> dict[str, Any]:
    chunks = chunk_text(text)
    created = 0
    for index, chunk in enumerate(chunks, start=1):
        terms = sorted(tokenize(chunk))
        db.add(
            KnowledgeChunk(
                source=source,
                category=category,
                title=f"{title} #{index}" if len(chunks) > 1 else title,
                content=chunk,
                embedding=json.dumps({"terms": terms}, ensure_ascii=False),
            )
        )
        created += 1
    await db.commit()
    return {"created": created, "chunks": created, "title": title, "source": source, "category": category}


async def retrieve_knowledge(
    db: AsyncSession,
    query: str,
    *,
    top_k: int = 5,
    category: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(KnowledgeChunk).order_by(KnowledgeChunk.created_at.desc()).limit(3000)
    if category:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.category == category).order_by(KnowledgeChunk.created_at.desc()).limit(3000)
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    query_terms = tokenize(query)
    scored: list[dict[str, Any]] = []
    for chunk in chunks:
        try:
            payload = json.loads(chunk.embedding or "{}")
            chunk_terms = set(payload.get("terms") or [])
        except json.JSONDecodeError:
            chunk_terms = tokenize(chunk.content)
        score = score_chunk(query_terms, chunk_terms, chunk.content)
        if score <= 0:
            continue
        scored.append(
            {
                "id": chunk.id,
                "title": chunk.title,
                "source": chunk.source,
                "category": chunk.category,
                "content": chunk.content,
                "score": score,
                "created_at": str(chunk.created_at),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def format_rag_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "无"
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        content = chunk["content"][:900]
        lines.append(f"[{index}] {chunk['title']} | {chunk['source']} | score={chunk['score']}\n{content}")
    return "\n\n".join(lines)
