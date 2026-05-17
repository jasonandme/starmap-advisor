from __future__ import annotations

from typing import Any

from app.data.akshare_stock import get_stock_quote
from app.skills.base import BaseSkill


class StockQuoteSkill(BaseSkill):
    name = "stock_quote"
    description = "获取 A 股个股实时行情，主要用于基金持仓穿透分析。"

    async def execute(self, code: str) -> dict[str, Any]:
        return await get_stock_quote(code)
