from __future__ import annotations

from typing import Any

from app.data.akshare_fund import get_fund_holdings
from app.skills.base import BaseSkill


class FundHoldingSkill(BaseSkill):
    name = "fund_holding"
    description = "获取基金披露的持仓股票明细，用于分析行业和个股集中度。"

    async def execute(self, code: str, year: str | None = None) -> dict[str, Any]:
        return await get_fund_holdings(code, year=year)
