import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict

# 加载 .env 文件中的环境变量
load_dotenv()


class HelloAgentsLLM:
    """
    为本书 "Hello Agents" 定制的LLM客户端。
    它用于调用任何兼容OpenAI接口的服务，并默认使用流式响应。
    """

    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """
        初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载。
        """
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout)

    def think(self, messages: List[Dict[str, str]], temperature: float = 0, reasoning_split=True) -> str:
        """
        调用大语言模型进行思考，并返回其响应。
        """
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
                extra_body={
                    "thinking": {
                        "type": "enabled",
                    },
                }
            )

            # 处理流式响应
            print("✅ 大语言模型响应成功:")
            collected_content = []
            for chunk in response:
                if getattr(chunk.choices[0].delta, "reasoning_content", None):
                    print(chunk.choices[0].delta.reasoning_content, end='')

                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content or ""
                    print(content, end="", flush=True)
                    collected_content.append(content)
            print()  # 在流式输出结束后换行
            return "".join(collected_content)

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None


# --- 客户端使用示例 ---
if __name__ == '__main__':
    try:
        llmClient = HelloAgentsLLM()

        exampleMessages = [
            {"role": "system",
             "content": "You are a helpful assistant that writes Python code."},
            {"role": "user", "content": "你好"}
        ]

        exampleMessages = [
            {'content': '''基于以下搜索结果为用户提供完整、准确的答案：

             用户问题：理解：用户想了解北京明天的天气情况以及适合游玩的景点推荐。
        搜索词：北京明天天气, 北京旅游景点推荐
        臺灣 護照
    
        

        请要求：
        1.
        综合搜索结果，提供准确、有用的回答
        2.
        如果是技术问题，提供具体的解决方案或代码
        3.
        引用重要信息的来源
        4.
        回答要结构清晰、易于理解
        5.
        如果搜索结果不够完整，请说明并提供补充建议
        ''', 'role': 'user'}
        ]
        print("--- 调用LLM ---")
        responseText = llmClient.think(exampleMessages)
        if responseText:
            print("\n\n--- 完整模型响应 ---")
            print(responseText)

    except ValueError as e:
        print(e)
