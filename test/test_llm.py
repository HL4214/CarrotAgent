from src.core.llm_client import CarrotLLMClient

if __name__ == '__main__':
    llm = CarrotLLMClient()

    message = [{"role": "user", "content": "你好"}]
    llm.stream(message)