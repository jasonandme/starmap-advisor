"""
星图智顾 - Pydantic 模型：基金相关
"""
from pydantic import BaseModel, Field
from datetime import date, datetime


class FundBrief(BaseModel):
    """基金摘要信息"""
    code: str = Field(description="基金代码")
    name: str = Field(description="基金名称")
    fund_type: str | None = Field(None, description="基金类型")
    nav: float | None = Field(None, description="最新净值")
    day_return: float | None = Field(None, description="日涨幅(%)")
    year_return: float | None = Field(None, description="近1年涨幅(%)")


class FundDetail(BaseModel):
    """基金详细信息"""
    code: str
    name: str
    full_name: str | None = None
    fund_type: str | None = None
    manager: str | None = None
    company: str | None = None
    setup_date: date | None = None
    nav: float | None = None
    acc_nav: float | None = None
    nav_date: date | None = None
    day_return: float | None = None
    week_return: float | None = None
    month_return: float | None = None
    three_month_return: float | None = None
    six_month_return: float | None = None
    year_return: float | None = None
    fee_rate: float | None = None
    scale: float | None = None


class FundNavPoint(BaseModel):
    """净值数据点"""
    date: str
    nav: float
    acc_nav: float | None = None
    daily_return: float | None = None


class FundHolding(BaseModel):
    """基金持仓明细"""
    stock_code: str
    stock_name: str
    hold_ratio: float = Field(description="占净值比(%)")
    hold_amount: float | None = Field(None, description="持股数(万股)")
    hold_value: float | None = Field(None, description="持仓市值(万元)")
    quarter: str | None = Field(None, description="报告期")


class FundCompareRequest(BaseModel):
    """基金对比请求"""
    codes: list[str] = Field(min_length=2, max_length=5, description="基金代码列表")


class FundRankQuery(BaseModel):
    """基金排名查询"""
    fund_type: str = Field(default="全部", description="基金类型")
    top_n: int = Field(default=20, ge=1, le=100, description="返回数量")
