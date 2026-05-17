from __future__ import annotations

from typing import Any

from app.data.akshare_fund import get_fund_rank
from app.skills.base import BaseSkill


class FundRankSkill(BaseSkill):
    name = "fund_rank"
    description = "获取指定基金类型的排名数据，支持全部、股票型、混合型、债券型、指数型、QDII。"

    async def execute(self, fund_type: str = "全部", top_n: int = 20) -> dict[str, Any]:
        return await get_fund_rank(fund_type=fund_type, top_n=top_n)
