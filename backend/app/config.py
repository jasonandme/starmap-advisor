"""
星图智顾 - 配置管理
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置，从 .env 文件和环境变量中读取"""

    # === 应用基础 ===
    APP_NAME: str = "星图智顾"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # === DeepSeek（主力模型） ===
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_REASONER_MODEL: str = "deepseek-reasoner"

    # === 通义千问（备选） ===
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    # === Kimi / Moonshot（备选） ===
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "moonshot-v1-32k"

    # === 当前激活的 LLM ===
    ACTIVE_LLM: str = "deepseek"  # "deepseek" | "qwen" | "kimi"

    # === 数据库 ===
    DATABASE_URL: str = "sqlite+aiosqlite:///./starmap.db"

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379/0"

    # === 数据缓存时间（秒） ===
    CACHE_QUOTE_TTL: int = 600       # 基金净值等低频行情缓存 10 分钟
    CACHE_STOCK_QUOTE_TTL: int = 30  # A 股实时快照缓存 30 秒
    CACHE_FUND_ESTIMATE_TTL: int = 20 # 基金持仓估算缓存 20 秒
    CACHE_FUND_HOLDING_TTL: int = 7 * 24 * 3600 # 披露持仓/资产配置缓存 7 天
    CACHE_RANK_TTL: int = 3600       # 排名缓存 1 小时
    CACHE_FUND_LIST_TTL: int = 86400 # 基金列表缓存 1 天

    model_config = {
        "env_file": (".env", "../.env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
