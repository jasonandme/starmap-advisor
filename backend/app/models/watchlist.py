"""
星图智顾 - ORM 模型：自选基金
"""
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class Watchlist(Base):
    """自选基金"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False, index=True, comment="基金代码")
    fund_name = Column(String(100), comment="基金名称")
    note = Column(Text, comment="备注")
    added_at = Column(DateTime, server_default=func.now())
