from rich.console import Console

console = Console()

from rich import print_json
# 专门格式化 JSON 字符串
print_json('{"name": "Carrot", "type": "Agent", "skills": ["Logic", "Vision"]}')

from rich.columns import Columns
from rich.panel import Panel

items = [Panel(f"任务 {i}", expand=False) for i in range(1)]
console.print(Columns(items))

from rich.syntax import Syntax

code = """
def eat_carrot():
    print("Crunchy!")
"""
# theme 参数可以换成 'monokai', 'github-dark' 等
syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
console.print(syntax)