"""星图智顾 - Skills 包。"""

from app.skills.base import BaseSkill, SkillResult
from app.skills.registry import register_default_skills, skill_registry

__all__ = ["BaseSkill", "SkillResult", "skill_registry", "register_default_skills"]
