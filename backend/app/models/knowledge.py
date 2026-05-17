"""
星图智顾 - ORM 模型：向量知识库
"""
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class KnowledgeChunk(Base):
    """知识库文本块（用于 RAG 检索）"""
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(200), comment="来源文件/URL")
    category = Column(String(50), comment="分类：fund_basics/market_analysis/methodology")
    title = Column(String(200), comment="标题")
    content = Column(Text, nullable=False, comment="文本内容")
    # embedding 暂用 JSON 存储，后续可迁移到 pgvector
    embedding = Column(Text, comment="向量（JSON 字符串）")
    created_at = Column(DateTime, server_default=func.now())
