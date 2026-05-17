from __future__ import annotations

from typing import Any

from app.data.akshare_news import get_market_flash, get_stock_news
from app.skills.base import BaseSkill


class NewsFetchSkill(BaseSkill):
    name = "news_fetch"
    description = "获取个股新闻或市场快讯，只作为辅助证据，不单独触发买卖建议。"

    async def execute(self, code: str | None = None, limit: int = 10) -> dict[str, Any]:
        if code:
            return await get_stock_news(code, limit=limit)
        return await get_market_flash(limit=limit)
