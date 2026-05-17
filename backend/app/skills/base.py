"""
星图智顾 - Skill 基类
所有 Skill 必须继承此基类，保证统一的执行、重试和日志记录。
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any
import time
import logging

logger = logging.getLogger(__name__)


class SkillResult(BaseModel):
    """Skill 统一返回结构"""
    success: bool
    data: Any | None = None
    error: str | None = None
    latency_ms: int = 0
    skill_name: str = ""


class BaseSkill(ABC):
    """
    Skill 抽象基类。
    每个 Skill 负责一个明确的数据获取或计算任务。
    """
    name: str = ""
    description: str = ""
    max_retries: int = 2
    timeout_seconds: int = 15

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        执行 Skill 的核心逻辑。
        子类必须实现此方法。
        """
        ...

    async def run(self, **kwargs) -> SkillResult:
        """
        带重试和计时的执行入口。
        不要直接覆写此方法，覆写 execute() 即可。
        """
        start = time.monotonic()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await self.execute(**kwargs)
                ms = int((time.monotonic() - start) * 1000)
                logger.info(f"Skill [{self.name}] 成功 | {ms}ms")
                return SkillResult(
                    success=True,
                    data=result,
                    latency_ms=ms,
                    skill_name=self.name,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Skill [{self.name}] 第{attempt + 1}次尝试失败: {e}"
                )
                if attempt < self.max_retries:
                    # 简单退避
                    import asyncio
                    await asyncio.sleep(0.5 * (attempt + 1))

        ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Skill [{self.name}] 最终失败 | {ms}ms | {last_error}")
        return SkillResult(
            success=False,
            error=str(last_error),
            latency_ms=ms,
            skill_name=self.name,
        )
