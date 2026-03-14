"""
LLMClient类

LLMClient类是一个用于与大型语言模型（LLM）进行交互的客户端类。它提供了一个接口，使用户能够发送请求并接收来自LLM的响应。该类可以用于各种应用场景，如自然语言处理、文本生成、对话系统等。
"""
import os
from typing import Dict, List

from openai import OpenAI

from ..utils import logger


class CarrotLLMClient(object):
    def __init__(self,
                 model: str = None,
                 base_url: str = None,
                 api_key: str = None,
                 temperature: float = None,
                 timeout: int = None,
                 max_tokens: int = None,
                 **kwargs
                 ):
        """
        初始化LLM客户端
        :param base_url:
        :param api_key:
        :param temperature:
        :param timeout:
        :param max_tokens:
        :param kwargs:
        """
        self.model = model or os.getenv("LLM_MODEL", "gpt-4")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.timeout = timeout or os.getenv("LLM_TIMEOUT", 30)
        self.max_tokens = max_tokens or os.getenv("LLM_MAX_TOKENS", 128000)
        self.temperature = temperature or os.getenv("LLM_TEMPERATURE", 0.7)

        # 创建OpenAI客户端
        self._client = self._create_client()
        logger.info("LLMClient initialized with model: {}, base_url: {}, timeout: {}, max_tokens: {}".format(
            self.model, self.base_url, self.timeout, self.max_tokens))

    def _create_client(self):
        return OpenAI(api_key=self.api_key,
                      base_url=self.base_url,
                      timeout=self.timeout)

    def think(self,
              messages,
              stream=True,
              **kwargs):
        """
        调用llm进行思考，并返回流失响应
        :param messages:
        :param stream:
        :return:
        """
        logger.info("LLMClient thinking with messages: {}".format(messages))

        try:
            requests_kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": stream

            }
            # TODO:添加tools相关信息
            response = self._client.chat.completions.create(**requests_kwargs)

            logger.debug(f"LLM响应成功,流失响应:{stream}")
            for chunk in response:
                content = chunk.choices[0].delta.get("content", "")
                if content:
                    yield content

        except Exception as e:
            logger.error("LLMClient think error: {}".format(e))
            raise e

    def invoke(self,
               messages: List[Dict[str, str]],
               **kwargs):

        content = self.think(messages=messages,
                             stream=False,
                             **kwargs)
        return content

    def stream(self,
               messages: List[Dict[str, str]],
               **kwargs):
        content = ""
        logger.debug("LLM 流式响应:\n")
        for content_part in self.stream(messages=messages,
                                        stream=True,
                                        **kwargs):
            print(content_part, end="", flush=True)
            content += content_part
        return content
