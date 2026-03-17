from src.agents.code_agent import CodeAgent
from src.core import CarrotLLMClient, Config
from src.tools.registry import ToolsRegistry

if __name__ == '__main__':
    code_agent = CodeAgent(
        name="CarrotAgent",
        llm_client=CarrotLLMClient(),
        tool_registry=ToolsRegistry(),
        project_root="./",
        config=Config(),
        system_prompt="You are a helpful assistant.",
    )

    input = "创建一个output.txt文件，并在内部写入test。"
    response = code_agent.run(input_text=input, show_raw=True)
    print(response)
