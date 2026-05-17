"""
星图智顾 - ORM 模型：组合与投资偏好
"""
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class PortfolioItem(Base):
    """个人持仓或候选基金条目。"""

    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False, default="", index=True, comment="基金代码")
    fund_name = Column(String(160), nullable=False, comment="基金名称")
    source = Column(String(40), nullable=False, default="manual", comment="来源")
    amount = Column(Float, nullable=False, default=0.0, comment="当前持仓金额")
    yesterday_profit = Column(Float, nullable=True, comment="昨日收益")
    holding_profit = Column(Float, nullable=True, comment="持有收益")
    holding_return_pct = Column(Float, nullable=True, comment="持有收益率")
    tags = Column(JSON, default=list, comment="标签")
    confidence = Column(String(40), nullable=False, default="manual", comment="数据置信度")
    is_holding = Column(Boolean, nullable=False, default=False, comment="是否持有")
    is_watchlist = Column(Boolean, nullable=False, default=True, comment="是否自选")
    notes = Column(Text, nullable=False, default="", comment="备注")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InvestmentPreference(Base):
    """投资偏好与组合约束。"""

    __tablename__ = "investment_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    risk_profile = Column(String(24), nullable=False, default="balanced", comment="风险档位")
    strategy_goal = Column(String(40), nullable=False, default="balanced_growth", comment="策略目标")
    max_single_fund_pct = Column(Float, nullable=False, default=12.0, comment="单只基金最大仓位")
    max_qdii_pct = Column(Float, nullable=False, default=30.0, comment="QDII 最大仓位")
    allow_sector_funds = Column(Boolean, nullable=False, default=True, comment="是否允许行业主题基金")
    max_drawdown_pct = Column(Float, nullable=False, default=15.0, comment="最大可接受回撤")
    max_theme_pct = Column(Float, nullable=False, default=40.0, comment="行业主题基金最大仓位")
    min_cash_pct = Column(Float, nullable=False, default=10.0, comment="现金/低波仓位下限")
    rebalance_frequency = Column(String(24), nullable=False, default="monthly", comment="再平衡频率")
    notes = Column(Text, nullable=False, default="", comment="备注")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PortfolioAction(Base):
    """基金级操作记录或计划。"""

    __tablename__ = "portfolio_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, nullable=True, index=True, comment="组合条目 ID")
    fund_code = Column(String(10), nullable=False, default="", index=True, comment="基金代码")
    fund_name = Column(String(160), nullable=False, default="", comment="基金名称")
    action_type = Column(String(32), nullable=False, comment="操作类型")
    amount = Column(Float, nullable=True, comment="操作金额")
    target_fund_code = Column(String(10), nullable=False, default="", comment="转换目标基金代码")
    target_fund_name = Column(String(160), nullable=False, default="", comment="转换目标基金名称")
    schedule = Column(String(64), nullable=False, default="", comment="定投周期或执行计划")
    status = Column(String(24), nullable=False, default="planned", comment="状态")
    reason = Column(Text, nullable=False, default="", comment="操作理由")
    metadata_json = Column(JSON, default=dict, comment="扩展信息")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PortfolioImport(Base):
    """截图/拍照导入记录。"""

    __tablename__ = "portfolio_imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(260), nullable=False, comment="原始文件名")
    saved_path = Column(String(500), nullable=False, comment="保存路径")
    source_type = Column(String(32), nullable=False, default="holding", comment="导入类型")
    status = Column(String(32), nullable=False, default="uploaded", comment="处理状态")
    extracted_text = Column(Text, nullable=False, default="", comment="OCR 文本")
    parsed_items = Column(JSON, default=list, comment="解析出的条目")
    message = Column(Text, nullable=False, default="", comment="处理说明")
    created_at = Column(DateTime, server_default=func.now())
