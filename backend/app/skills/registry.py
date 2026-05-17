"""
星图智顾 - Skill 注册表
集中管理所有可用的 Skill 实例，供 Agent 和 API 调用。
"""
from app.skills.base import BaseSkill
from app.skills.fund_compare import FundCompareSkill
from app.skills.fund_detail import FundDetailSkill
from app.skills.fund_holding import FundHoldingSkill
from app.skills.fund_rank import FundRankSkill
from app.skills.fund_recommend import FundRecommendSkill
from app.skills.fund_search import FundSearchSkill
from app.skills.news_fetch import NewsFetchSkill
from app.skills.stock_quote import StockQuoteSkill


class SkillRegistry:
    """Skill 注册表"""

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        """注册一个 Skill"""
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill | None:
        """按名称获取 Skill"""
        return self._skills.get(name)

    def list_all(self) -> list[dict]:
        """列出所有已注册的 Skill"""
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]

    @property
    def names(self) -> list[str]:
        return list(self._skills.keys())


# 全局单例
skill_registry = SkillRegistry()


def register_default_skills() -> SkillRegistry:
    """注册默认 skill。重复调用是安全的。"""
    for skill in [
        FundSearchSkill(),
        FundRankSkill(),
        FundDetailSkill(),
        FundCompareSkill(),
        FundHoldingSkill(),
        FundRecommendSkill(),
        StockQuoteSkill(),
        NewsFetchSkill(),
    ]:
        skill_registry.register(skill)
    return skill_registry


register_default_skills()
