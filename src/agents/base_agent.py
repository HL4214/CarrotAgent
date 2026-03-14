import abc
from typing import Optional, List

from ..core import Config, CarrotLLMClient, Message
from ..tools.registry import ToolsRegistry


class BaseAgent(abc.ABC):
    def __init__(self,
                 name: str,
                 llm_client: CarrotLLMClient,
                 tool_registry: ToolsRegistry,
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None):
        self.name = name
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.config = config
        self._history: List[Message] = []

    @abc.abstractmethod
    def run(self, input_text: str, **kwargs)->str:
        pass

    def add_message(self, message: Message):
        """添加消息到历史记录"""
        self._history.append(message)

    def clear_history(self):
        """清空历史记录"""
        self._history.clear()

    def get_history(self) -> list[Message]:
        """获取历史记录"""
        return self._history.copy()

    def __str__(self) -> str:
        return f"Agent(name={self.name})"

    def __repr__(self) -> str:
        return self.__str__()
