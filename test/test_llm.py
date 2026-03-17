from src.core.llm_client import CarrotLLMClient
from src.core.env import load_env

load_env()

if __name__ == '__main__':
    llm = CarrotLLMClient()

    message = [{"role": "user", "content": "你好"}]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. Chicago, IL",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            }
        }
    ]

    messages = [{"role": "user", "content": "What's the weather like in Chicago today?"}]
    llm.invoke(messages)