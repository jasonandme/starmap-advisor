"""
星图智顾 - ORM 模型：分析记录
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class Analysis(Base):
    """AI 分析记录"""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="分析标题")
    query = Column(Text, nullable=False, comment="用户提问")
    response = Column(Text, nullable=False, comment="AI 回答")
    skills_used = Column(JSON, default=[], comment="使用的 Skill 列表")
    fund_codes = Column(JSON, default=[], comment="涉及的基金代码")
    created_at = Column(DateTime, server_default=func.now())
