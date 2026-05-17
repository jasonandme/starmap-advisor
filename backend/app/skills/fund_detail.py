from __future__ import annotations

from typing import Any

from app.data.akshare_fund import get_fund_detail
from app.skills.base import BaseSkill


class FundDetailSkill(BaseSkill):
    name = "fund_detail"
    description = "获取单只基金的净值走势、近期收益、回撤和波动指标。"

    async def execute(self, code: str) -> dict[str, Any]:
        return await get_fund_detail(code)
