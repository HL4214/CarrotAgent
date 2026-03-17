import json
import os
from pathlib import Path
from typing import Union, Optional, Any

from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PtStyle
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax

from rich.theme import Theme
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.columns import Columns

import sys

from rich.tree import Tree

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 尝试导入 pyfiglet 以生成艺术字
try:
    from pyfiglet import Figlet

    HAS_FIGLET = True
except ImportError:
    HAS_FIGLET = False

from src.agents.code_agent import CodeAgent
from src.core import CarrotLLMClient, Config
from src.tools.registry import ToolsRegistry
from src.utils.ui_components import UIComponent

# Geeky Theme
custom_theme = Theme({
    "info": "bright_cyan",
    "warning": "bright_yellow",
    "error": "bold bright_red",
    "user": "bold bright_green",
    "agent": "bold bright_blue",
    "banner": "bold bright_blue",
    "thinking": "italic bright_magenta",
    "action": "bold bright_cyan",
    "observation": "dim",
})

console = Console(theme=custom_theme)


class RichConsoleCodeAgent(CodeAgent):
    """
    基于Rich和Prompt_toolkit构建的Cli Agent界面
    """

    def __init__(self, name: str,
                 llm_client: CarrotLLMClient,
                 tool_registry: ToolsRegistry,
                 project_root: Union[str, Path],
                 system_prompt: Optional[str] = None,
                 config: Optional[Config] = None,
                 ui: Optional[UIComponent] = None):
        super().__init__(name,
                         llm_client,
                         tool_registry,
                         project_root,
                         system_prompt,
                         config)
        self.ui = ui

    def run(self,
            input_text: str,
            **kwargs) -> str:
        if self.ui:
            self.ui.reset_before_run()
            self.ui.start_run(input_tokens=0)

        try:
            response = super().run(input_text, **kwargs)
        finally:
            if self.ui:
                self.ui.end_run(output_tokens=0)
                self.ui.show_tool_calls()
        return response

    def _execute_tool(self, tool_name: str, tool_input: Any):
        # 先将工具调用信息保存，最后执行完成后统一打印
        self.ui.add_tool_call(tool_name=tool_name, tool_input=tool_input)

        # 打印工具的调用结果
        with console.status(f"[bold cyan]Executing {tool_name}...[/bold cyan]", spinner="dots"):
            response = super()._execute_tool(tool_name, tool_input)
            console.print(f"[success]✓ Execution {tool_name} completed![/success]")
        return response

    def _console(self, message: str) -> None:
        # console.print(message, style="info")
        if "🎬 Action:" in message:
            # Action is usually followed by content, let's parse it
            content = message.split("🎬 Action:", 1)[-1].strip()
            console.print(Panel(Text(content, style="bold cyan"), title="[action]Action[/action]", border_style="cyan",
                                title_align="left"))
        elif "👀 Observation:" in message:
            content = message.split("👀 Observation:", 1)[-1].strip()
            # Truncate if too long for display, but keep enough context
            if len(content) > 1000:
                content = content[:1000] + "\n... (remaining content truncated for display)"

            # Attempt to highlight code if it looks like code
            if content.strip().startswith("{") or content.strip().startswith("["):
                try:
                    json.loads(content)
                    renderable = Syntax(content, "json", theme="monokai", word_wrap=True)
                except:
                    renderable = Text(content, style="dim")
            else:
                renderable = Text(content, style="dim")

            console.print(Panel(renderable, title="[observation]Observation[/observation]", border_style="dim",
                                title_align="left"))
        else:
            console.print(message)

def create_carrot_banner():
    """为 CarrotAgent 定制的启动横幅"""

    # 1. 生成 ASCII 艺术字 (Carrot)
    if HAS_FIGLET:
        f = Figlet(font='big')
        ascii_art = f.renderText("CARROT")
    else:
        # 手动设计的胡萝卜风格艺术字
        ascii_art = r"""
  _____                            _   
 / ____|                          | |  
| |     __ _ _ __ _ __ ___   ___ | |_ 
| |    / _` | '__| '__/ _ \ / _ \| __|
| |___| (_| | |  | | | (_) | (_) | |_ 
 \_____\__,_|_|  |_|  \___/ \___/ \__|
        """

    # 2. 颜色设计：使用胡萝卜的经典配色（橙色身子 + 绿色叶子）
    # 顶部叶子感
    leaf_decor = Text("  \\\\\\ ///\n   \\\\V//\n", style="bold green")

    # 主体文字样式
    banner_text = Text(ascii_art, style="bold #FF8700")  # 橙色

    # 副标题
    subtitle = Text("\n🥕 Your Crunchy & Smart AI Assistant", style="italic white")
    status_line = Text("\n[ System: Online ] [ Mode: Agile ]", style="dim cyan")

    # 组合 Banner 内容
    full_content = Text.assemble(leaf_decor, banner_text, subtitle, status_line)

    # 3. 装饰元素：在左右两侧各放一个胡萝卜 Emoji
    decorated_content = Align.center(full_content)

    # 4. 渲染到面板中
    banner_panel = Panel(
        decorated_content,
        border_style="#4E9A06",  # 深绿色边框，代表叶子
        padding=(1, 4),
        title="[bold #FF8700]v1.0.0[/bold #FF8700]",
        title_align="left",
        subtitle="[bold white]CarrotAgent CLI[/bold white]",
        subtitle_align="center"
    )

    console.print(banner_panel)


def ui_init():
    """
    启动时初始化UI
    :return:
    """
    create_carrot_banner()
    return UIComponent(console=console)


pt_style = PtStyle.from_dict({
    'prompt': 'bold #00aa00',
    'at': '#666666',
    'username': '#00afff',
})


def get_prompt_message():
    """自定义输入提示符"""
    return HTML("<username>User</username><at>@</at><prompt>cli> </prompt>")


def _print_assistant_response(text: str) -> None:
    md = Markdown(text)
    console.print(Panel(md, title="[agent]Assistant[/agent]", border_style="blue", expand=False))


def main():
    ui = ui_init()

    # 创建带历史记录的会话
    working_dir = os.getcwd()
    history_file = os.path.join(working_dir, ".chat_history")
    session = PromptSession(history=FileHistory(history_file))

    # 初始化agent
    agent = RichConsoleCodeAgent(
        name="CarrotAgent",
        llm_client=CarrotLLMClient(),
        tool_registry=ToolsRegistry(),
        project_root=working_dir,
        # system_prompt="You are a helpful assistant.",
        config=Config(),
        ui=ui
    )
    while True:
        try:
            # 获取用户输入
            user_input = session.prompt(
                get_prompt_message(),
                style=pt_style
            ).strip()

            if not user_input:
                continue

            # 调用agent获取输出
            response = agent.run(user_input)
            # 格式化打印输出
            _print_assistant_response(response)
            console.print("\n" + "─" * console.width + "\n", style="grey37")

        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    main()
