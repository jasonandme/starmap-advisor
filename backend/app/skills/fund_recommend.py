from __future__ import annotations

from typing import Any

from app.data.akshare_fund import recommend_funds
from app.skills.base import BaseSkill


class FundRecommendSkill(BaseSkill):
    name = "fund_recommend"
    description = "根据基金类型和风险偏好生成可解释候选池。"

    async def execute(
        self,
        fund_type: str = "QDII",
        risk_preference: str = "balanced",
        top_n: int = 5,
    ) -> dict[str, Any]:
        return await recommend_funds(
            fund_type=fund_type,
            risk_preference=risk_preference,
            top_n=top_n,
        )
