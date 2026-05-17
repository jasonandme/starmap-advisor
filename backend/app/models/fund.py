"""
星图智顾 - ORM 模型：基金主数据
"""
from sqlalchemy import Column, String, Float, Date, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class Fund(Base):
    """基金主数据"""
    __tablename__ = "funds"

    code = Column(String(10), primary_key=True, comment="基金代码")
    name = Column(String(100), nullable=False, comment="基金简称")
    full_name = Column(String(200), comment="基金全称")
    fund_type = Column(String(20), comment="基金类型：股票型/混合型/债券型/指数型/QDII/货币型")
    manager = Column(String(100), comment="基金经理")
    company = Column(String(100), comment="基金公司")
    setup_date = Column(Date, comment="成立日期")
    nav = Column(Float, comment="最新单位净值")
    acc_nav = Column(Float, comment="累计净值")
    nav_date = Column(Date, comment="净值日期")
    day_return = Column(Float, comment="日涨幅(%)")
    week_return = Column(Float, comment="近1周涨幅(%)")
    month_return = Column(Float, comment="近1月涨幅(%)")
    three_month_return = Column(Float, comment="近3月涨幅(%)")
    six_month_return = Column(Float, comment="近6月涨幅(%)")
    year_return = Column(Float, comment="近1年涨幅(%)")
    fee_rate = Column(Float, comment="管理费率(%)")
    scale = Column(Float, comment="基金规模(亿元)")
    metadata_json = Column(JSON, default={}, comment="扩展元数据")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
