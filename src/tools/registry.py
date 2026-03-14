"""
工具注册类
"""
import os
from typing import Dict, Any, TypedDict, Callable

from ..utils import logger
from ..tools.base import Tool
from .circuit_breaker import CircuitBreaker


class ReadMeta(TypedDict):
    """Read 操作的元信息（用于乐观锁自动注入）"""
    path_resolved: str  # 解析后的规范化路径（主键）
    file_mtime_ms: int  # 文件修改时间（毫秒）
    file_size_bytes: int  # 文件大小（字节）
    captured_at: float  # 缓存时间戳（用于调试/过期策略）


class ToolsRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._functions: Dict[str, dict[str, Any]] = {}

        # Read操作的元信息缓存，用于乐观锁检查
        self._read_cache: dict[str, ReadMeta]
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "3")),
            recovery_timeout=int(os.getenv("CIRCUIT_RECOVERY_TIMEOUT", "300")),
        )

    def register_tool(self, tool: Tool) -> None:
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"Tool with name '{tool.name}' is already registered. Overwriting.")

        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def register_function(self,
                          name: str,
                          description: str,
                          func: Callable[[str], str]
                          ):
        if name not in self._functions:
            logger.warning(f"Function with name '{name}' is already registered. Overwriting.")
        self._functions[name] = {
            "description": description,
            "func": func
        }
        logger.info(f"Registered function: {name}")

    def unregister(self, name: str):
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
        elif name in self._functions:
            del self._functions[name]
            logger.info(f"Unregistered function:{name}")
        else:
            logger.warning(f"{name} not registered")
