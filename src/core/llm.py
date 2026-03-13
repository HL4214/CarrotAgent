import os
from typing import Optional, Iterator
from openai import OpenAI

from src.utils.exception import LLMException
from src.utils.logger import default_logger


class CarrotLLMClient:

    def __init__(self,
                 model: Optional[str] = None,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 temperature: float = 0.7,
                 max_tokens: Optional[int] = None,
                 timeout: Optional[int] = None,
                 **kwargs
                 ):
        """
        初始化LLM客户端

        :param model:
        :param base_url:
        :param api_key:
        :param temperature:
        :param max_tokens:
        :param timeout:
        :param kwargs:
        """
        # 使用传入参数，未传入则从环境变量中加载
        self.model = model or os.getenv("LLM_MODEL_ID")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.kwargs = kwargs

        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

        self._client = self._create_client()

    def _create_client(self):
        """
        目前只支持OpenAI的接口，后面考虑接入Anthropic等接口类型
        :return:
        """
        return OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout
        )

    def think(self, messages: list[dict[str, str]], temperature: Optional[float] = None) -> Iterator[str]:
        """
        调用大语言模型进行思考，并返回流式响应。
        这是主要的调用方法，默认使用流式响应以获得更好的用户体验。

        Args:
            messages: 消息列表
            temperature: 温度参数，如果未提供则使用初始化时的值

        Yields:
            str: 流式响应的文本片段
        """
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            # 处理流式响应
            print("✅ 大语言模型响应成功:")
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    print(content, end="", flush=True)
                    yield content
            print()  # 在流式输出结束后换行

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            raise LLMException(f"LLM调用失败: {str(e)}")

    def invoke(self, messages: list[dict[str, str]], **kwargs):
        """
        同步全量返回结果

        :return:
        """
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                **self.kwargs,
                **kwargs
            )
            content = response.choices[0].message.content
            default_logger.log_llm_message(messages, content)
            return content
        except Exception as e:
            default_logger.error(f"LLM调用失败: {str(e)}")
            raise LLMException(f"LLM调用失败: {str(e)}")

    def stream(self, messages: list[dict[str, str]], **kwargs) -> str:
        """
        流式调用LLM的别名方法，与think方法功能相同。
        保持向后兼容性。
        """
        temperature = kwargs.get('temperature')
        response = ''
        for content in self.think(messages,temperature):
            response += content
        return response
        # yield from self.think(messages, temperature)


if __name__ == '__main__':
    # 简单测试
    from dotenv import load_dotenv
    load_dotenv()

    client = CarrotLLMClient()
    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "请介绍一下你自己。"}
    ]
    client.stream(messages, temperature=0.7)
    # for chunk in client.think(messages):
    #     pass  # 已经在think方法中打印了响应内容
