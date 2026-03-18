import abc
import json
import traceback
from pathlib import Path
from random import choices
from typing import Optional, List, Any, Dict, Tuple, Union

from ..core import Config, CarrotLLMClient, Message
from ..core.context import ContextBuilder
from ..tools.registry import ToolsRegistry
from ..utils import logger
from ..utils.trace_doubao import create_trace_logger, StepType


class BaseAgent(abc.ABC):
    def __init__(self,
                 name: str,
                 llm_client: CarrotLLMClient,
                 tool_registry: ToolsRegistry,
                 project_root: Union[str, Path],
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None):
        self.name = name
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.config = config

        # 工作沙箱配置，一般就是工作目录
        self.project_root = project_root

        self._history: List[Message] = []

        # 上下文构建器
        self.context_builder = ContextBuilder(
            tool_registry=self.tool_registry,
            project_root=self.project_root,
            system_prompt_override=self.system_prompt,
        )

        self.logger = logger
        self.trace_logger = create_trace_logger()
        self._system_messages_logged = False
        self._system_messages_override: Optional[List[dict]] = None

    @abc.abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
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

    @staticmethod
    def extract_content(raw_response: Any) -> Optional[str]:
        """
        从LLM响应中解析非思考内容
        :param response:
        :return:
        """
        try:
            if hasattr(raw_response, "choices"):
                content = raw_response.choices[0].message.content
                if isinstance(content, list):
                    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
                return content
        except Exception:
            logger.error(f"Error when extract content from response: {traceback.print_exc()}")
            return None

    @staticmethod
    def extract_usage(raw_response: Any) -> Optional[Dict]:
        """
        从LLM响应中解析 usage,返回token使用数量
        :param response:
        :return:
        """
        try:
            if hasattr(raw_response, "usage"):
                usage = raw_response.usage
                if not usage:
                    return None
                return {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None)
                }
        except Exception as E:
            logger.error(f"Error when extract usage from response: {E},error trace:{traceback.print_exc()}")
            return None

    @staticmethod
    def extract_tool_calls(raw_response) -> List[Dict[str, Any]]:
        """
        从LLM原始响应中解析工具调用列表
        :param raw_response:
        :return:
        """

        def get_attr(obj, key: str):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get("key", None)
            return getattr(obj, key, None)

        try:
            choices = get_attr(raw_response, "choices")
            if not choices:
                return []
            choice = choices[0]
            message = get_attr(choice, "message")
            if not message:
                return []
            tool_calls = get_attr(message, "tool_calls")
            calls: list[dict[str, Any]] = []
            if tool_calls:
                for tool_call in tool_calls:
                    fn = get_attr(tool_call, "function")
                    fn_name = get_attr(fn, "name")
                    arguments = get_attr(fn, "arguments")
                    call_id = get_attr(tool_call, "id")
                    calls.append({
                        "id": call_id,
                        "name": fn_name,
                        "arguments": arguments,
                        "extra_content": get_attr(tool_call, "extra_content")
                    })

            return calls
        except Exception as e:
            logger.error(f"Error when extract tool calls from response, error:{e}, error trace:{traceback.print_exc()}")
            return []

    @staticmethod
    def parse_tool_params(raw_arguments: Union[str, Dict, List]) -> Tuple[Any, Optional[str]]:
        if raw_arguments is None:
            return {}, None
        if isinstance(raw_arguments, (dict, list)):
            return raw_arguments, None

        s = str(raw_arguments).strip()
        if not s:
            return {}, None
        try:
            return json.loads(s), None
        except Exception as e:
            return {}, str(e)

    def _execute_tool(self, tool_name: str, tool_input: Any):
        res = self.tool_registry.execute_tool(tool_name, tool_input)
        return str(res)

    def _log_system_messages_if_needed(self) -> None:
        """
        记录系统消息,因为系统消息在最多只记录一次。
        :return:
        """
        if self._system_messages_logged or not self.trace_logger:
            return
        system_messages = self._get_system_messages_for_run()
        self.trace_logger.record_system(system_messages)
        self._system_messages_logged = True

    def _get_system_messages_for_run(self) -> List[dict]:
        if self._system_messages_override:
            return [dict(m) for m in self._system_messages_override]
        return self.context_builder.get_system_messages()

    def __str__(self) -> str:
        return f"Agent(name={self.name})"

    def __repr__(self) -> str:
        return self.__str__()
