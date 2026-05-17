from __future__ import annotations

from typing import Any

from app.data.akshare_fund import search_funds
from app.skills.base import BaseSkill


class FundSearchSkill(BaseSkill):
    name = "fund_search"
    description = "按基金代码、名称或类型搜索公募基金。"

    async def execute(self, query: str, limit: int = 20) -> dict[str, Any]:
        return await search_funds(query, limit=limit)
