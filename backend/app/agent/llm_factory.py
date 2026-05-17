"""
星图智顾 - LLM 工厂
根据配置创建对应的 LangChain LLM 实例。
"""
from langchain_openai import ChatOpenAI
from app.config import Settings, get_settings
import logging

logger = logging.getLogger(__name__)


def get_llm(settings: Settings | None = None, purpose: str = "chat", provider: str | None = None):
    """
    根据配置创建 LLM 实例。
    DeepSeek 和通义千问都兼容 OpenAI 接口，统一用 ChatOpenAI。
    """
    if settings is None:
        settings = get_settings()

    active = (provider or settings.ACTIVE_LLM).lower()
    if active == "moonshot":
        active = "kimi"

    if active == "deepseek":
        model = settings.DEEPSEEK_REASONER_MODEL if purpose == "reasoner" else settings.DEEPSEEK_MODEL
        logger.info(f"使用 DeepSeek: {model}")
        return ChatOpenAI(
            model=model,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.2 if purpose == "reasoner" else 0.3,
            max_tokens=8192 if purpose == "reasoner" else 4096,
        )
    elif active == "qwen":
        logger.info(f"使用通义千问: {settings.QWEN_MODEL}")
        return ChatOpenAI(
            model=settings.QWEN_MODEL,
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL,
            temperature=0.3,
            max_tokens=4096,
        )
    elif active == "kimi":
        logger.info(f"使用 Kimi: {settings.KIMI_MODEL}")
        return ChatOpenAI(
            model=settings.KIMI_MODEL,
            api_key=settings.KIMI_API_KEY,
            base_url=settings.KIMI_BASE_URL,
            temperature=0.2 if purpose == "reasoner" else 0.3,
            max_tokens=8192 if purpose == "reasoner" else 4096,
        )
    else:
        raise ValueError(f"不支持的 LLM 类型: {active}")
