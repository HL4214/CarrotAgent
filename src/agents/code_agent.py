import os
from pathlib import Path
from typing import Optional, Any, Union

from .base_agent import BaseAgent
from ..core.context import ContextBuilder
from ..core.context.history_manager import HistoryManager
from ..core.context.summary_compressor import create_summary_generator
from ..core import CarrotLLMClient, Config
from ..core.skills import SkillLoader
from ..tools.registry import ToolsRegistry
from ..tools.builtin import *
from ..utils import logger


class CodeAgent(BaseAgent):
    def __init__(self,
                 name: str,
                 llm_client: CarrotLLMClient,
                 tool_registry: ToolsRegistry,
                 project_root: Union[str, Path],
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None):
        super().__init__(name,
                         llm_client,
                         tool_registry,
                         system_prompt,
                         config)
        # 工作沙箱配置
        self.project_root = project_root

        self.logger = logger
        self.last_response_raw: Optional[Any] = None

        # Debug选项
        self.verbose = bool(self.config.debug)
        self.console_verbose = bool(self.config.show_agent_steps)
        self.console_progress = bool(self.config.show_progess)

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
        self._skill_loader = SkillLoader(self.project_root)
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

        # Trace日志，后续使用LangSmith实现

    def _refresh_skills_prompt(self) -> None:
        refresh = os.getenv("SKILLS_REFRESH_ON_CALL", "true").lower() in {"1", "true", "yes", "y", "on"}
        if refresh:
            self._skill_loader.refresh_if_stale()
        elif not self._skills_prompt:
            self._skill_loader.scan()
        budget = int(os.getenv("SKILLS_PROMPT_CHAR_BUDGET", "12000"))
        self._skills_prompt = self._skill_loader.format_skills_for_prompt(budget)

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
            **kwargs) ->str:
        pass
