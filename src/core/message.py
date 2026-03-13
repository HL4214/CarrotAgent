from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel

# 定义消息角色的类型，限制其取值
# TODO::命名限制会降低灵活性，后续考虑添加更多角色类别或者去除该限制，但是需要注意，在许多国产大模型API接口中，角色类别是固定的。
MessageRole = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    """
    消息类
    """
    content: str
    role: MessageRole
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self, content: str, role: MessageRole, **kwargs):
        super().__init__(
            content=content,
            role=role,
            timestamp=kwargs.get('timestamp', datetime.now()),
            metadata=kwargs.get('metadata', {})
        )
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content
        }

    def __str__(self):
        return f"[{self.role}] {self.content}"
