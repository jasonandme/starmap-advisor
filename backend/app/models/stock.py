"""
星图智顾 - ORM 模型：股票主数据（辅助基金持仓分析）
"""
from sqlalchemy import Column, String, Float, Date, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class Stock(Base):
    """股票主数据"""
    __tablename__ = "stocks"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), nullable=False, comment="股票名称")
    market = Column(String(10), comment="市场：SH/SZ")
    industry = Column(String(50), comment="所属行业")
    price = Column(Float, comment="最新价")
    change_pct = Column(Float, comment="涨跌幅(%)")
    pe = Column(Float, comment="市盈率")
    pb = Column(Float, comment="市净率")
    market_cap = Column(Float, comment="总市值(亿)")
    metadata_json = Column(JSON, default={}, comment="扩展元数据")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
