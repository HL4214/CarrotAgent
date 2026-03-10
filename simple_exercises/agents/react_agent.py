import re

from src.core.llm import HelloAgentsLLM
from src.tools.tool_executor import ToolExecutor

REACT_PROMPT_TEMPLATE = """
请注意，你是一个有能力调用外部工具的智能助手。

可用工具如下：
{tools}

请严格按照以下格式回应：

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步的行动。
Action: 你决定采取的行动，必须是以下格式之一：
- '{{tool_name}}[{{tool_input}}]':调用一个可用工具。
- 'Finish[最终答案]'：当你认为已经得到了足够的信息来回答用户的问题时，使用这个格式来提供最终答案。
- 当你收集到足够的信息，能够直接回答用户的问题时，你必须在Action:字段后使用 Finish[最终答案]的格式来提供答案。

现在，请开始解决以下问题：
Question: {question}
History: {history}
"""


class ReactAgent:
    def __init__(self,
                 llm_client: HelloAgentsLLM,
                 tool_executor: ToolExecutor,
                 max_steps: int = 5
                 ):
        """ Initialize the ReactAgent.

        Args:
            llm_client (HelloAgentsLLM): llm client instance for generating responses.
            tool_executor (ToolExecutor): tool executor instance for executing available tools.
            max_steps (int, optional): maximum number of steps to take. Defaults to 5.
        """
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history = []

    def _parse_output(self, text: str):
        """ Parse the output from the LLM.

        Args:
            text (str): The raw output from the LLM.

        Returns:
            _type_: _description_
        """
        thought_match = re.search(
            r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL)
        action_match = re.search(r"Action:\s*(.*?)$", text, re.DOTALL)

        thought = thought_match.group(1).strip() if thought_match else ""
        action = action_match.group(1).strip() if action_match else ""
        return thought, action

    def _parse_action(self, action: str):
        """ parse the action to determine if it's a tool call or a final answer.

        Args:
            action (str): action string from the LLM output.
        """
        match = re.match(r"(\w+)\[(.*)\]", action)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def run(self, question: str) -> str:
        """
        Run the ReactAgent to solve a question.

        Args:
            question (str): The question to be answered.

        Returns:
            str: The final answer.
        """
        self.history = []
        current_step = 0

        while current_step < self.max_steps:
            # 格式化提示词
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=self.tool_executor.get_available_tools(),
                question=question,
                history="\n".join(self.history)
            )

            # 调用LLM进行思考回复
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.think(messages=messages)
            if not response:
                print("LLM did not return a response. Ending agent execution.")
                break

            thought, action = self._parse_output(response)
            if thought:
                print(f"解析Thought: {thought}")

            if not action:
                print("No action found in LLM response. Ending agent execution.")
                break

            # 执行Action
            if action.startswith("Finish"):
                final_answer = re.match(r"Finish\[(.*)\]", action).group(1)
                print(f"Final Answer: {final_answer}")
                return final_answer

            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                print("Invalid action format. Ending agent execution.")
                break

            print(f"Executing tool: {tool_name} with input: {tool_input}")

            tool_function = self.tool_executor.get_tool(tool_name)
            if not tool_function:
                observation = f"Tool '{tool_name}' not found."
            else:
                observation = tool_function(tool_input)
            print(f"Observation: {observation}")

            # 将本轮的Action和Observation添加到历史中
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")
        print(
            "Reached maximum steps without finding a final answer. Ending agent execution.")
        return None


if __name__ == "__main__":
    llm_client = HelloAgentsLLM()
    tool_executor = ToolExecutor()
    # 注册工具
    from src.tools.search import search
    tool_executor.register_tool("Search", "使用Google搜索查询信息", search)

    agent = ReactAgent(llm_client=llm_client, tool_executor=tool_executor)

    question = "英伟达最新的GPU型号是什么？"
    final_answer = agent.run(question)
