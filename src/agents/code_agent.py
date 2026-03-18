import json
import logging
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Optional, Any, Union, List, Dict

from .base_agent import BaseAgent
from ..core.context import ContextBuilder
from ..core.context.history_manager import HistoryManager
from ..core.context.summary_compressor import create_summary_generator
from ..core.context.input_preprocessor import preprocess_input
from ..core import CarrotLLMClient, Config
from ..core.skills import SkillLoader
from ..tools.registry import ToolsRegistry
from ..tools.builtin import *
from ..utils import logger
from ..utils.trace_doubao import StepType


class CodeAgent(BaseAgent):
    def __init__(self,
                 name: str,
                 llm_client: CarrotLLMClient,
                 tool_registry: ToolsRegistry,
                 project_root: Union[str, Path],
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None):
        super().__init__(name=name,
                         llm_client=llm_client,
                         tool_registry=tool_registry,
                         system_prompt=system_prompt,
                         config=config,
                         project_root=project_root
                         )

        self.last_response_raw: Optional[Any] = None

        # Debug选项
        self.verbose = bool(self.config.debug)
        self.console_verbose = bool(self.config.show_agent_steps)
        self.console_progress = bool(self.config.show_progress)

        # Cli交互配置
        self.interactive = os.getenv("AGENT_INTERACTIVE", "true").lower() in {"1", "true", "yes", "y", "on"}

        # 创建Summary生成器，TODO:这部分是不是应该放到ContextEngine中,在agent创建一个ContextEngine的实例
        summary_generator = create_summary_generator(
            llm=self.llm_client,
            config=self.config,
            verbose=self.verbose
        )

        # 历史上下文管理
        self.history_manager = HistoryManager(
            config=self.config,
            summary_generator=summary_generator
        )

        # Skills
        self._skill_loader = SkillLoader(config.skill_dir)
        self._skills_prompt = ""
        self._refresh_skills_prompt()

        # 注册工具
        # TODO:后续当工具数量过多的时候，考虑使用检索等方式选择工具，而不是现有的将所有工具描述都放进上下文中
        self._register_builtin_tools()
        self._mcp_tools_prompt = ""
        # TODO:注册MCP工具

        # 上下文构建器
        self.context_builder = ContextBuilder(
            tool_registry=self.tool_registry,
            project_root=self.project_root,
            system_prompt_override=self.system_prompt,
            mcp_tools_prompt=self._mcp_tools_prompt,
            skills_prompt=self._skills_prompt,
        )

    def _refresh_skills_prompt(self) -> None:
        """
        刷新技能描述,可实时刷新
        :return:
        """
        logger.debug("Refreshing Skills Prompt...")
        refresh = os.getenv("SKILLS_REFRESH_ON_CALL", "true").lower() in {"1", "true", "yes", "y", "on"}
        if refresh:
            self._skill_loader.refresh_if_stale()
        elif not self._skills_prompt:
            self._skill_loader.scan()
        budget = int(os.getenv("SKILLS_PROMPT_CHAR_BUDGET", "12000"))
        self._skills_prompt = self._skill_loader.format_skills_for_prompt(budget)
        logger.debug(f"Skills Prompt: {self._skills_prompt}")

    def _register_builtin_tools(self):
        """注册内置工具"""
        self.tool_registry.register_tool(
            ListFilesTool(project_root=self.project_root,
                          working_dir=self.project_root)
        )
        self.tool_registry.register_tool(SearchFilesByNameTool(project_root=self.project_root))
        self.tool_registry.register_tool(GrepTool(project_root=self.project_root))
        self.tool_registry.register_tool(ReadTool(project_root=self.project_root))
        self.tool_registry.register_tool(WriteTool(project_root=self.project_root))
        self.tool_registry.register_tool(EditTool(project_root=self.project_root))
        self.tool_registry.register_tool(MultiEditTool(project_root=self.project_root))
        self.tool_registry.register_tool(TodoWriteTool(project_root=self.project_root))
        self.tool_registry.register_tool(
            SkillTool(project_root=self.project_root, skill_loader=self._skill_loader)
        )
        self.tool_registry.register_tool(BashTool(project_root=self.project_root))
        self.tool_registry.register_tool(
            AskUserTool(project_root=self.project_root, interactive=self.interactive)
        )

        # # Task tool for subagent delegation
        # self.tool_registry.register_tool(
        #     TaskTool(
        #         project_root=self.project_root,
        #         main_llm=self.llm,
        #         tool_registry=self.tool_registry,
        #         team_manager=self.team_manager,
        #     )
        # )
        # if self.enable_agent_teams:
        #     self._register_agent_teams_tools()

    def run(self,
            input_text: str,
            **kwargs) -> str:
        """

        CodeAgent处理流程：
        1. 预处理用户输入 (@file 解析)
        2. 检查是否需要压缩上下文
        3. 将用户消息写入 上下文中
        4. 运行Agent循环。
        5. 返回最终结果

        :param input_text:
        :param kwargs:
        :return:
        """
        show_raw = kwargs.pop("show_raw", False)
        if self.console_progress:
            self._console("⏳ Agent 正在处理，请稍候...")

        # 1.预处理用户输入(@file 解析)
        processed_input = self.process_user_input(input_text)
        self._log_system_messages_if_needed()  # 记录系统消息至日志中
        self.trace_logger.record_user_input(user_input={"raw_user_input": input_text,
                                                        "processed_user_input": processed_input})  # 记录用户输入

        # 2.将用户消息写入history内
        self.history_manager.append_user(processed_input)
        # TODO:添加trace记录

        if self.console_verbose:
            self._console(f"\n⚙️ Engine 启动: {input_text}")
        elif self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Engine 启动: %s", input_text)

        response_text = ""
        try:
            response_text = self._run_loop(pending_input=processed_input,
                                           show_raw=show_raw)
        except Exception as e:
            traceback.print_exc()
            raise ValueError(f"运行错误: {e}")

        # self.trace_logger.export_to_html()
        return response_text

    def _run_loop(self,
                  pending_input: str,
                  show_raw: bool) -> str:
        """
        Agent循环，
        目前采用ReAct的方式，规划由大模型自己判断是否调用TODOList的工具

        步骤：
        1. 构建 LLM输入Messages: L1系统级 + L2规则约束提示词 + L3历史上下文
        2. 判断是否要研所，若压缩以后则根据压缩内容重新构造上下文。
        3. 调用LLM,工具调用依赖LLM自己的function calling。
        4. 解析LLM结果，分为Thought/Action.
        5. 若为Finish,则返回结果。
        6. 若为工具调用：则执行工具。将assistant + tool消息追加到History中。
        :return:
        """
        # TODO:目前只支持React的方式，后面要支持先和模型通过plan对话的方式

        tool_choice = "auto"
        for step in range(1, self.config.max_loop_steps):
            # 将工具描述转换为function calling schema，使工具能够被支持原生function calling的LLM调用
            tools_schema: List[Dict[str, Any]] = self.tool_registry.get_openai_tools_schema()

            if self.console_verbose:
                self._console(f"\n--- Step {step}/{self.config.max_loop_steps} ---")
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("Step %d/%d", step, self.config.max_loop_steps)

            # 每次循环开始前，判断是否需要压缩上下文
            if self.history_manager.should_compress(pending_input):
                if self.console_verbose:
                    self._console("\n📦 触发历史压缩...")
                self.logger.debug("触发历史压缩")

                estimated_tokens = self.history_manager.estimate_context_tokens(pending_input)
                # self.trace_logger.("history_compression_triggered", {
                #     "estimated_tokens": estimated_tokens,
                #     "threshold": threshold,
                #     "total_usage_tokens": self.history_manager.get_total_usage_tokens(),
                #     "message_count": self.history_manager.get_message_count(),
                # }, step=step)

                rounds_before = self.history_manager.get_rounds_count()
                messages_before = self.history_manager.get_message_count()
                compress_info = self.history_manager.compact(on_event=None,
                                                             return_info=True)
                compressed = bool(compress_info.get("compressed"))

                if compressed:
                    rounds_after = self.history_manager.get_rounds_count()
                    messages_after = self.history_manager.get_message_count()
                    compressed_history = self.history_manager.to_messages()
                    final_context = self.context_builder.build_messages(compressed_history)

            # 构建 messages 列表
            history_messages = self.history_manager.to_messages()
            messages = self._build_messages(history_messages)
            base_messages = messages
            logger.warning("重新构建messages")
            # TODO:记录构建后的上下文

            response_text = ""
            reasoning_content = ""
            tool_calls: list[dict[str, Any]] = []

            """====================解析LLM原始响应===================="""
            while True:
                # 返回LLM原始响应，从原始响应中解析usage、functionCalling等信息
                raw_response = self.llm_client.invoke_raw(messages=messages,
                                                          tools=tools_schema,
                                                          tool_choice=tool_choice)
                if show_raw:
                    # TODO:记录原始响应
                    print("raw_response:", raw_response)
                    pass

                # TODO：解析思考响应和正式回复

                # 更新token使用量
                usage = self.extract_usage(raw_response)
                if usage and usage.get("total_tokens") is not None:
                    self.history_manager.update_last_usage(usage["total_tokens"])
                # 解析工具调用
                response_text = self.extract_content(raw_response)
                tool_calls = self.extract_tool_calls(raw_response)

                self.trace_logger.add_step(
                    step_type=StepType.LLM_RESPONSE,
                    content={
                        "tool_calls": tool_calls,
                        "response": response_text
                    },
                )
                if tool_calls or response_text:
                    break

            # 若无工具调用且无回复，则结束循环
            if not tool_calls and not response_text:
                break

            """====================处理工具调用===================="""
            if tool_calls:
                for call in tool_calls:
                    if not call.get("id"):
                        call["id"] = f"call_{uuid.uuid4().hex}"

                assistant_content = str(response_text)
                self.history_manager.append_assistant(
                    content=assistant_content,
                    metadata={
                        "step": step,
                        "action_type": "tool_call",
                        "tool_calls": tool_calls,
                    },
                    reasoning_content=reasoning_content,
                )
                for call in tool_calls:
                    tool_name = call.get("name", "unknown_tool")
                    tool_call_id = call.get("id", f"call_{uuid.uuid4().hex}")
                    raw_args = call.get("arguments", {})
                    tool_input, parse_err = self.parse_tool_params(raw_args)
                    if parse_err:
                        error_result = {
                            "status": "error",
                            "error": {"code": "INVALID_PARAM", "message": f"Tool arguments parse error: {parse_err}"},
                            "data": {},
                        }
                        observation = json.dumps(error_result, ensure_ascii=False)
                        self.logger.error("解析工具参数错误: %s", parse_err)
                    else:
                        try:
                            if self.console_verbose:
                                self._console(f"\n🎬 Action: {tool_name}[{tool_input}]\n")
                            elif self.logger.isEnabledFor(logging.DEBUG):
                                self.logger.debug("Action: %s %s", tool_name, tool_input)

                            observation = self._execute_tool(tool_name, tool_input)
                            try:
                                self._console(f"👀 Observation: {observation}")
                                result_obj = json.loads(observation)
                                self.trace_logger.add_step(step_type=StepType.TOOL_RESPONSE,
                                                           content=result_obj)
                            except json.JSONDecodeError:
                                logger.error("工具返回结果不是json: %s", observation)
                        except Exception as e:
                            error_result = {
                                "status": "error",
                                "error": {"code": "EXECUTION_ERROR", "message": str(e)},
                                "data": {}}
                            observation = json.dumps(error_result, ensure_ascii=False)
                            logger.error("执行工具错误: %s", e)

                    self.history_manager.append_tool(tool_name=tool_name,
                                                     raw_result=observation,
                                                     metadata={
                                                         "step": step,
                                                         "tool_call_id": tool_call_id,
                                                     },
                                                     project_root=self.project_root)
                continue

            # FIXME: 当前逻辑只会调用一次LLM。对于需要多次调用LLM的场景，需要修改。比如第二次的工具需要依赖第一次的输出，需要将第一次的输出重新输入到LLM中去。

            # 无工具调用
            final_text = str(response_text).strip()
            self.history_manager.append_assistant(
                content=final_text,
                metadata={
                    "step": step,
                    "action_type": "final",
                },
                reasoning_content=reasoning_content,
            )
            return final_text
        return "抱歉，我无法在限定步数内完成该任务。"

    def _build_messages(self, history_messages: list[dict]) -> list[dict]:
        system_messages = self._get_system_messages_for_run()
        return list(system_messages) + list(history_messages)

    def process_user_input(self, input_text):
        """
        预处理用户输入
        :param input_text:
        :return:
        """
        # 重现加载技能提示，确保获取的是最新的技能提示
        self._refresh_skills_prompt()
        self.context_builder.set_skills_prompt(self._skills_prompt)

        # 处理用户的输入，包含一些引用的文件
        preprocess_result = preprocess_input(input_text)
        processed_input = preprocess_result.processed_input

        if preprocess_result.mentioned_files:
            mentioned = ", ".join(preprocess_result.mentioned_files)
            if self.console_verbose:
                self._console(f"\n📎 检测到文件引用: {mentioned}")
                if preprocess_result.truncated_count > 0:
                    self._console(f"   (另有 {preprocess_result.truncated_count} 个文件被省略)")
            elif self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("检测到文件引用: %s", mentioned)
                if preprocess_result.truncated_count > 0:
                    self.logger.debug("另有 %d 个文件被省略", preprocess_result.truncated_count)

        return processed_input

    def _console(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)
