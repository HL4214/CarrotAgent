from src.core.llm import HelloAgentsLLM
from typing import List, Dict, Any, Optional


class Memory:
    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def add_record(self, record_type: str, content: str):
        """_summary_

        Args:
            record_type (str): _description_
            content (str): _description_
        """
        self.records.append({"type": record_type, "content": content})
        print(f"🧠 记忆已更新,记录类型：{record_type},记录内容：{content}")

    def get_trajectory(self) -> List[Dict[str, Any]]:
        """_summary_

        Returns:
            List[Dict[str, Any]]: _description_
        """
        trajectory_parts = []
        for record in self.records:
            if record["type"] == "execution":
                trajectory_parts.append(f"上一轮的尝试结果为: {record['content']}")
            elif record["type"] == "reflection":
                trajectory_parts.append(f"评审员的反馈结果为：{record['content']}")
            else:
                raise ValueError(f"未知的记录类型: {record['type']}")
        return '\n\n'.join(trajectory_parts)

    def get_last_trajectory(self) -> Optional[str]:
        """_summary_

        Returns:
            Optional[str]: _description_
        """
        for record in reversed(self.records):
            if record['type'] == 'execution':
                return record['content']
        return None


INITIAL_PROMPT_TEMPLATE = """
你是一位资深的Python程序员。请根据以下要求，编写一个Python函数。
你的代码必须包含完整的函数签名、文档字符串，并遵循PEP 8编码规范。

要求: {task}

请直接输出代码，不要包含任何额外的解释。
"""

REFLECT_PROMPT_TEMPLATE = """
你是一位极其严格的代码评审专家和资深算法工程师，对代码的性能有极致的要求。
你的任务是审查以下Python代码，并专注于找出其在<strong>算法效率</strong>上的主要瓶颈。

# 原始任务:
{task}

# 待审查的代码:
```python
{code}
```

请分析该代码的时间复杂度，并思考是否存在一种<strong>算法上更优</strong>的解决方案来显著提升性能。
如果存在，请清晰地指出当前算法的不足，并提出具体的、可行的改进算法建议（例如，使用筛法替代试除法）。
如果代码在算法层面已经达到最优，才能回答“无需改进”。

请直接输出你的反馈，不要包含任何额外的解释。
"""


REFINE_PROMPT_TEMPLATE = """
你是一位资深的Python程序员。你正在根据一位代码评审专家的反馈来优化你的代码。

# 原始任务:
{task}

# 你上一轮尝试的代码:
{last_code_attempt}
评审员的反馈：
{feedback}

请根据评审员的反馈，生成一个优化后的新版本代码。
你的代码必须包含完整的函数签名、文档字符串，并遵循PEP 8编码规范。
请直接输出优化后的代码，不要包含任何额外的解释。
"""


class ReflectionAgent:
    def __init__(self,
                 llm_client: HelloAgentsLLM,
                 max_iterations: int = 5):
        self.llm_client = llm_client
        self.memory = Memory()
        self.max_iterations = max_iterations

    def _get_llm_response(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.think(messages)
        return response

    def run(self, task):
        print("任务开始：{task}")

        # 先调用初始代码执行逻辑
        init_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        print("\n正在执行初始推理...")
        init_response = self._get_llm_response(init_prompt)
        self.memory.add_record("execution", init_response)

        for iteration in range(self.max_iterations):
            print(f"\n=== 迭代 {iteration + 1} ===")

            # 反馈评审
            print("\n正在进行代码评审...")
            relection_prompt = REFLECT_PROMPT_TEMPLATE.format(
                task=task,
                code=self.memory.get_last_trajectory()
            )
            relection_response = self._get_llm_response(relection_prompt)
            self.memory.add_record("reflection", relection_response)

            if "无需改进" in relection_response:
                print("\n代码已达到最优，无需进一步优化。")
                break

            print("\n正在进行优化")
            # 根据反馈评审修改
            refine_prompt = REFINE_PROMPT_TEMPLATE.format(
                task=task,
                last_code_attempt=self.memory.get_last_trajectory(),
                feedback=relection_response)
            refine_response = self._get_llm_response(refine_prompt)
            self.memory.add_record("execution", refine_response)

        final_code = self.memory.get_last_trajectory()
        print(f"\n最终代码：{final_code}")
        return final_code


if __name__ == "__main__":
    llm_client = HelloAgentsLLM()
    agent = ReflectionAgent(llm_client)

    task = "使用python实现一个快速排序算法"
    agent.run(task)
