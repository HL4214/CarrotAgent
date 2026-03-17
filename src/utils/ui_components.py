"""
ui组件相关内容
"""
import time

from rich.console import Console
from rich.text import Text
from rich.tree import Tree


class ThinkingTimer:
    """Real-time timer with token counter for model thinking process"""

    def __init__(self, console: Console):
        self.console = console
        self._start_time = None
        self._elapsed = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._running = False
        self._thread = None
        self._live = None

    def start(self, input_tokens: int = 0):
        """Start the timer"""
        self._start_time = time.time()
        self._elapsed = 0
        self._input_tokens = input_tokens
        self._output_tokens = 0
        self._running = True

    def update_output_tokens(self, tokens: int):
        """Update output token count"""
        self._output_tokens = tokens

    def stop(self) -> float:
        """Stop the timer and return elapsed time"""
        self._running = False
        if self._start_time:
            self._elapsed = time.time() - self._start_time
        return self._elapsed

    def get_display_text(self) -> Text:
        """Get the display text for the timer"""
        if self._running and self._start_time:
            elapsed = time.time() - self._start_time
        else:
            elapsed = self._elapsed

        text = Text()
        text.append("✻ ", style="bold yellow")

        if self._running:
            text.append("Calculating… ", style="bold yellow")
        else:
            text.append("Completed ", style="bold green")

        text.append(f"({int(elapsed)}s", style="dim")

        if self._input_tokens > 0:
            text.append(f" · ↑ {self._input_tokens}", style="cyan")
        if self._output_tokens > 0:
            text.append(f" · ↓ {self._output_tokens}", style="magenta")

        text.append(")", style="dim")
        return text


class UIComponent:
    def __init__(self, console: Console):
        self.tool_tree = Tree("🛠️  [bold cyan]Tool Calls[/bold cyan]")

        self.thinking_timer = ThinkingTimer(console=console)
        self.console = console

    def reset_before_run(self):
        """
        每次agent执行时进行reset
        :return:
        """
        self.tool_tree = Tree("🛠️  [bold cyan]Tool Calls[/bold cyan]")

    def start_run(self, input_tokens: int = 0):
        self.thinking_timer.start(input_tokens=input_tokens)
        self.console.print(self.thinking_timer.get_display_text())

    def end_run(self,output_tokens:int=0):
        self.thinking_timer.stop()
        self.console.print(self.thinking_timer.get_display_text())

    def add_tool_call(self, tool_name: str, tool_input: str):
        """
        添加工具调用信息
        :param tool_name:
        :param tool_input:
        :return:
        """
        tool_node = self.tool_tree.add(f"[bold cyan]🔧 {tool_name}[/bold cyan]")
        tool_node.add(f"[yellow]Input:[/yellow] {tool_input}")

    def show_tool_calls(self):
        self.console.print(self.tool_tree)