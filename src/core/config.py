"""
配置管理类
"""
import os

from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Config(BaseModel):
    """
    Agent配置类
    """
    # LLM配置
    default_model: str = os.environ.get("LLM_MODEL_ID", "gpt-4")
    temperature: float = float(os.environ.get("LLM_TEMPERATURE", 0.7))
    max_tokens: int = int(os.environ.get("MAX_TOKENS", 128000))

    # 系统配置
    debug: bool = False
    log_level: str = "INFO"
    show_agent_steps: bool = True
    show_progress: bool = True

    # 历史记录配置
    max_history_length: int = 100

    # 上下文工程配置
    context_window: int = int(os.environ.get("CONTEXT_WINDOW", 128000))  # 默认128K
    compression_threshold: float = float(os.environ.get("COMPRESSION_THRESHOLD", 0.8))
    min_retain_rounds: int = 10
    summary_timeout: int = 120
    tool_message_format: str = "strict"

    # Agent配置
    max_loop_steps: int = 50

    # Skill配置
    skill_dir: str = os.environ.get("SKILL_DIR", "D:\workfile\CarrotAgent\skills")