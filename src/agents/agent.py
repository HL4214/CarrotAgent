"""
Agent基类

定义一个智能体应该具备的通用属性和行为
"""
import abc
import re
from abc import ABC
from typing import Optional, List, Dict

from hello_agents.tools import ToolRegistry

from src.core.config import Config
from src.core.llm import CarrotLLMClient
from src.core.message import Message
from src.utils import default_logger
from src.utils.exception import AgentException


class BaseAgent(ABC):
    """
    Agent基类，定义智能体的通用属性和行为
    """

    def __init__(self,
                 agent_name: str,
                 llm_client: CarrotLLMClient,
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None,
                 ):
        """

        :param agent_name:
        :param llm_client:
        :param system_prompt:
        :param config:
        """
        self.agent_name = agent_name
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.config = config

        self._history_messages: List[Message] = []

    @abc.abstractmethod
    def run(self, input_text, **kwargs):
        raise NotImplementedError

    def add_message(self, message: Message):
        self._history_messages.append(message)

    def clear_history(self):
        self._history_messages.clear()

    def get_history(self) -> List[Message]:
        return self._history_messages.copy()

    def __str__(self):
        return f"Agent(name={self.agent_name}, llm_model={self.llm_client.model})"


class SimpleAgent(BaseAgent):
    def __init__(self,
                 agent_name: str,
                 llm_client: CarrotLLMClient,
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None,
                 tool_registry: Optional['ToolRegistry'] = None,
                 enable_tool_calling: bool = True):
        super().__init__(agent_name,
                         llm_client,
                         system_prompt,
                         config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling
        default_logger.info(f"初始化Agent {agent_name}成功")

    def _get_enhanced_system_prompt(self) -> str:
        """构建增强的系统提示词，包含工具信息"""
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"

        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt

        # 获取工具描述
        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        tools_section = "\n\n## 可用工具\n"
        tools_section += "你可以使用以下工具来帮助回答问题:\n"
        tools_section += tools_description + "\n"

        tools_section += "\n## 工具调用格式\n"
        tools_section += "当需要使用工具时，请使用以下格式:\n"
        tools_section += "`[TOOL_CALL:{tool_name}:{parameters}]`\n"
        tools_section += "例如:`[TOOL_CALL:search:Python编程]` 或 `[TOOL_CALL:memory:recall=用户信息]`\n\n"
        tools_section += "工具调用结果会自动插入到对话中，然后你可以基于结果继续回答。\n"

        return base_prompt + tools_section

    def run(self, input_text, max_tool_iterations: int = 3, **kwargs):
        """
        重写运行算法
        :param input_text:
        :param max_tool_iterations: 最大工具调用迭代次数，防止无限循环
        :param kwargs:
        :return:
        """
        default_logger.info(f"Agent {self.agent_name} 收到输入: {input_text}")

        messages = []

        # 添加系统消息
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        messages.append(dict(role="system", content=enhanced_system_prompt))

        # 添加历史消息
        for msg in self._history_messages:
            messages.append(dict(role=msg.role, content=msg.content))

        # 添加当前用户消息
        messages.append({"role": "user", "content": input_text})
        # TODO:: 1.在history_messages中只添加了user和assistant的消息，没有添加system的消息。2.messages和history_messages的Message对象和字典格式不一致，建议统一格式。
        # 如果没有启用工具调用，使用简单对话逻辑
        if not self.enable_tool_calling:
            response = self.llm_client.stream(messages, **kwargs)
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response, "assistant"))
            default_logger.debug(f"✅ {self.agent_name} 响应完成")
            return response

        # 支持多轮工具调用的逻辑
        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)

    @staticmethod
    def _parse_tool_calls(text: str):
        """
        解析文本中的工具调用指令，返回工具名称和参数列表
        :param text:
        :return:
        """
        pattern = r'\[TOOL_CALL:([^:]+):([^\]]+)\]'
        matches = re.findall(pattern, text)

        tool_calls = []
        for tool_name, parameters in matches:
            tool_calls.append(
                {
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'original': f'[TOOL_CALL:{tool_name}:{parameters}]'
                }
            )
        return tool_calls

    def _execute_tool_call(self,
                           tool_name: str,
                           parameters: str) -> str:
        """
        执行工具调用，返回工具结果
        :param tool_name:
        :param parameters:
        :return:
        """
        if not self.tool_registry:
            raise AgentException("错误：未配置工具注册表")

        try:
            # 参数解析
            # TODO:后续
            if tool_name == "calculator":
                result = self.tool_registry.execute_tool(tool_name, parameters)
            else:
                # 其他工具使用智能参数解析
                param_dict = self._parse_tool_parameters(tool_name, parameters)
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    return f"❌ 错误:未找到工具 '{tool_name}'"
                result = tool.run(param_dict)

            return f"🔧 工具 {tool_name} 执行结果:\n{result}"
        except Exception as e:
            return f"❌ 工具调用失败:{str(e)}"

    def _parse_tool_parameters(self, tool_name: str, parameters: str):
        """智能解析工具参数"""
        param_dict = {}

        if '=' in parameters:
            # 格式: key=value 或 action=search,query=Python
            if ',' in parameters:
                # 多个参数:action=search,query=Python,limit=3
                pairs = parameters.split(',')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        param_dict[key.strip()] = value.strip()
            else:
                # 单个参数:key=value
                key, value = parameters.split('=', 1)
                param_dict[key.strip()] = value.strip()
        else:
            # 直接传入参数，根据工具类型智能推断
            if tool_name == 'search':
                param_dict = {'query': parameters}
            elif tool_name == 'memory':
                param_dict = {'action': 'search', 'query': parameters}
            else:
                param_dict = {'input': parameters}

        return param_dict

    def _run_with_tools(self,
                        messages: list,
                        input_text: str,
                        max_tool_iterations: int, **kwargs) -> str:
        """支持工具调用的运行逻辑"""
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            # 调用LLM
            response = self.llm_client.stream(messages, **kwargs)

            # 检查是否有工具调用
            tool_calls = self._parse_tool_calls(response)

            if tool_calls:
                print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                # 执行所有工具调用并收集结果
                tool_results = []
                clean_response = response

                for call in tool_calls:
                    result = self._execute_tool_call(call['tool_name'], call['parameters'])
                    tool_results.append(result)
                    # 从响应中移除工具调用标记
                    clean_response = clean_response.replace(call['original'], "")

                # 构建包含工具结果的消息
                messages.append({"role": "assistant", "content": clean_response})

                # 添加工具结果
                tool_results_text = "\n\n".join(tool_results)
                messages.append({"role": "user", "content": f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"})

                current_iteration += 1
                continue

            # 没有工具调用，这是最终回答
            final_response = response
            break

        # 如果超过最大迭代次数，获取最后一次回答
        if current_iteration >= max_tool_iterations and not final_response:
            final_response = self.llm_client.stream(messages, **kwargs)

        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        print(f"✅ {self.agent_name} 响应完成")

        return final_response

    def add_tool(self, tool) -> None:
        """添加工具到Agent（便利方法）"""
        if not self.tool_registry:
            from hello_agents import ToolRegistry
            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        self.tool_registry.register_tool(tool)
        print(f"🔧 工具 '{tool.name}' 已添加")

    def has_tools(self) -> bool:
        """检查是否有可用工具"""
        return self.enable_tool_calling and self.tool_registry is not None

    def remove_tool(self, tool_name: str) -> bool:
        """移除工具（便利方法）"""
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
            return True
        return False

    def list_tools(self) -> list:
        """列出所有可用工具"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []