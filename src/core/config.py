"""
Config类

配置类，包含一些全局的配置项，可以在这里修改默认的配置项
"""

import os
from typing import Dict, Any

from pydantic import BaseModel


class Config(BaseModel):
    # LLM配置
    default_model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1024

    # 系统配置
    debug: bool = False
    log_level: str = "INFO"

    # 其它配置
    max_history_length: int = 100

    @classmethod
    def from_env(cls):
        """
        从环境变量加载配置项
        """
        return cls(
            temperature=float(os.getenv("LLM_TEMPERATURE", 0.7)),
            max_tokens=int(os.getenv("MAX_TOKENS")) if os.getenv("MAX_TOKENS") else None,
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_history_length=int(os.getenv("MAX_HISTORY_LENGTH", 100))
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.to_dict()
