from __future__ import annotations

from typing import Any

from app.data.akshare_fund import compare_funds
from app.skills.base import BaseSkill


class FundCompareSkill(BaseSkill):
    name = "fund_compare"
    description = "对比 2-5 只基金的净值走势、收益、回撤和波动。"

    async def execute(self, codes: list[str]) -> dict[str, Any]:
        return await compare_funds(codes)
