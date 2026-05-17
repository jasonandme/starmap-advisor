"""
星图智顾 - Pydantic 模型：对话相关
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(description="用户消息")
    conversation_id: str | None = Field(None, description="会话ID，为空则新建")
    history: list["ChatMessage"] = Field(default_factory=list, description="最近几轮上下文")
    deep_mode: bool = Field(False, description="是否使用深度问策模式")
    model_provider: str | None = Field(None, description="本次问策使用的模型供应商：deepseek/qwen/kimi")


class ChatMessage(BaseModel):
    """对话消息"""
    role: str = Field(description="角色：user/assistant/system")
    content: str = Field(description="消息内容")
    cards: list[dict] | None = Field(None, description="附带的结构化卡片数据")
