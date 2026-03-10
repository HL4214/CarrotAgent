from typing import Dict, Any


class ToolExecutor:
    """
    ToolExecutor is responsible for managing and executing tools. It maintains a registry of tools, where each tool is identified by a unique name and associated with its implementation details.
    """

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, description: str, func: callable):
        """ Registers a new tool with the executor.

        Args:
            name (str): The name of the tool.
            description (str): A brief description of the tool's functionality.
            func (callable): The function that implements the tool's behavior.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """

        if name in self.tools:
            raise ValueError(f"Tool with name '{name}' is already registered.")

        self.tools[name] = {
            "description": description,
            "func": func
        }
        print(f"Tool '{name}' registered successfully.")

    def get_tool(self, name: str) -> callable:
        """ Retrieves the function of a registered tool.

        Args:
            name (str): The name of the tool to retrieve.

        Returns:
            callable: The function that implements the tool's behavior.

        Raises:
            KeyError: If no tool with the specified name is found.
        """

        if name not in self.tools:
            raise KeyError(f"Tool with name '{name}' not found.")

        return self.tools[name].get("func")

    def get_available_tools(self) -> str:
        """ Retrieves a list of available tool names.

        Returns:
            str: A comma-separated string of available tool names.
        """
        return "\n".join(f"{name}: {details['description']}" for name, details in self.tools.items())


if __name__ == "__main__":
    from src.tools.search import search
    executor = ToolExecutor()
    executor.register_tool("Search", "使用Google搜索查询信息", search)
    print("Available tools:")
    print(executor.get_available_tools())

    # Example of executing a tool

    tool_input = "英伟达最新的GPU型号是什么？"
    print(f"Executing 'Search' tool with input: {tool_input}")

    tool_name = "Search"
    search_func = executor.get_tool(tool_name)
    if search_func:
        result = search_func(tool_input)
        print(f"Search result:\n{result}")
    else:
        print(f"Tool '{tool_name}' not found.")
