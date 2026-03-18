from InquirerPy import inquirer
from rich.console import Console

console = Console()

def inquirer_multi_select():
    selected = inquirer.checkbox(
        message="请选择要为 CarrotAgent 开启的模块：",
        choices=[
            "🔍 实时搜索 (Search)",
            "💻 代码执行 (Code Interpreter)",
            "🎨 图像生成 (Image Gen)",
        ],
        pointer=">",  # 使用简单的箭头
        enabled_symbol="[x]",  # 这种风格在 CLI 中非常经典且稳健
        disabled_symbol="[ ]",
        transformer=lambda result: f"{len(result)} 个模块已就绪" # 选中后的简短提示
    ).execute()

    console.print(f"最终选择: [bold orange1]{selected}[/]")

if __name__ == "__main__":
    inquirer_multi_select()