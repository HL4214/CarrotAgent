import abc
import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Dict, List

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """
    标准错误码枚举（遵循《通用工具响应协议》）
    """
    NOT_FOUND = "NOT_FOUND"  # 文件/路径不存在
    ACCESS_DENIED = "ACCESS_DENIED"  # 路径不在 project root 内（沙箱越界）
    PERMISSION_DENIED = "PERMISSION_DENIED"  # OS 权限不足（EACCES 等）
    INVALID_PARAM = "INVALID_PARAM"  # 参数校验失败（正则错误、类型错误等）
    TIMEOUT = "TIMEOUT"  # 工具在获取有效数据前超时
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 未分类的内部异常
    EXECUTION_ERROR = "EXECUTION_ERROR"  # 其它 I/O 或执行错误（磁盘满等）
    IS_DIRECTORY = "IS_DIRECTORY"  # 路径是目录而非文件
    BINARY_FILE = "BINARY_FILE"  # 文件是二进制格式
    CONFLICT = "CONFLICT"  # 文件在读取后被修改（乐观锁冲突）
    CIRCUIT_OPEN = "CIRCUIT_OPEN"  # 工具熔断中（临时禁用）
    ASK_USER_UNAVAILABLE = "ASK_USER_UNAVAILABLE"  # 子代理禁止交互
    MCP_PARAM_ERROR = "MCP_PARAM_ERROR"  # MCP 参数错误
    MCP_PARSE_ERROR = "MCP_PARSE_ERROR"  # MCP 解析错误
    MCP_EXECUTION_ERROR = "MCP_EXECUTION_ERROR"  # MCP 执行错误
    MCP_NETWORK_ERROR = "MCP_NETWORK_ERROR"  # MCP 网络错误
    MCP_TIMEOUT = "MCP_TIMEOUT"  # MCP 超时
    MCP_NOT_FOUND = "MCP_NOT_FOUND"  # MCP 工具不存在


class ToolStatus(str, Enum):
    """
    工具运行状态枚举（遵循《通用工具响应协议》）

    - SUCCESS: 任务完全按预期执行，无截断、无回退、无错误
    - PARTIAL: 结果可用但有"折扣"（截断/回退/部分失败）
    - ERROR: 无法提供有效结果（致命错误）
    """
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


class ToolParameter(BaseModel):
    """
    工具参数定义
    """
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class Tool(abc.ABC):
    """
    工具抽象类，所有工具都需要继承这个类
    """

    def __init__(self,
                 name: str,
                 description: str,
                 project_root: Optional[Path] = None,
                 working_dir: Optional[Path] = None):
        """
        初始化工具

        :param name:
        :param description:
        :param project_root:
        :param working_dir:
        """
        self.name = name
        self.description = description

        self._project_root = Path(project_root).resolve() if project_root else None
        self._working_dir = Path(working_dir).resolve() if working_dir else None

    @abc.abstractmethod
    def run(self, parameters: Dict[str, Any]):
        """
        执行工具
        :param parameters:
        :return:
        """
        pass

    def get_parameters(self) -> List[ToolParameter]:
        """
        获取工具参数定义
        :return:
        """
        pass

    def get_cwd_rel(self) -> str:
        """
        获取工作目录相对于项目根目录的路径

        用于填充 context.cwd 字段。

        Returns:
            相对路径字符串（失败时返回 "."）
        """
        if self._working_dir is None or self._project_root is None:
            return "."
        try:
            rel = self._working_dir.relative_to(self._project_root)
            return str(rel) if str(rel) else "."
        except ValueError:
            return "."

    # -------------------------------------------------------------------------
    # 响应构建辅助方法（遵循《通用工具响应协议》）
    # -------------------------------------------------------------------------

    def create_success_response(
            self,
            data: Dict[str, Any],
            text: str,
            params_input: Dict[str, Any],
            time_ms: int,
            extra_stats: Optional[Dict[str, Any]] = None,
            path_resolved: Optional[str] = None,
            extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建成功响应（status="success"）

        适用于任务完全按预期执行、无截断、无回退的场景。

        Args:
            data: 核心载荷（必须是对象，不允许 null）
            text: 给 LLM 阅读的格式化摘要
            params_input: 调用时传入的原始参数
            time_ms: 工具执行耗时（毫秒）
            extra_stats: 额外的统计字段
            path_resolved: 解析后的路径（如涉及路径解析）
            extra_context: 额外的上下文字段

        Returns:
            JSON 格式的响应字符串
        """
        return self._build_response(
            status=ToolStatus.SUCCESS,
            data=data,
            text=text,
            params_input=params_input,
            time_ms=time_ms,
            extra_stats=extra_stats,
            path_resolved=path_resolved,
            extra_context=extra_context,
        )

    def create_partial_response(
            self,
            data: Dict[str, Any],
            text: str,
            params_input: Dict[str, Any],
            time_ms: int,
            extra_stats: Optional[Dict[str, Any]] = None,
            path_resolved: Optional[str] = None,
            extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建部分成功响应（status="partial"）

        适用于结果可用但有"折扣"的场景：截断、回退、部分失败等。
        注意：data 中应包含 truncated/fallback 等标记说明原因。

        Args:
            data: 核心载荷（应包含截断/回退标记）
            text: 给 LLM 阅读的格式化摘要（应说明折扣原因和下一步建议）
            params_input: 调用时传入的原始参数
            time_ms: 工具执行耗时（毫秒）
            extra_stats: 额外的统计字段
            path_resolved: 解析后的路径
            extra_context: 额外的上下文字段

        Returns:
            JSON 格式的响应字符串
        """
        return self._build_response(
            status=ToolStatus.PARTIAL,
            data=data,
            text=text,
            params_input=params_input,
            time_ms=time_ms,
            extra_stats=extra_stats,
            path_resolved=path_resolved,
            extra_context=extra_context,
        )

    def create_error_response(
            self,
            error_code: ErrorCode,
            message: str,
            params_input: Dict[str, Any],
            time_ms: int = 0,
            data: Optional[Dict[str, Any]] = None,
            path_resolved: Optional[str] = None,
            extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建错误响应（status="error"）

        适用于工具无法提供有效结果的场景。
        注意：error 字段仅在此情况下存在。

        Args:
            error_code: 标准错误码
            message: 人类可读的错误消息
            params_input: 调用时传入的原始参数
            time_ms: 工具执行耗时（毫秒）
            path_resolved: 解析后的路径
            extra_context: 额外的上下文字段

        Returns:
            JSON 格式的响应字符串
        """
        # 构建 context
        context: Dict[str, Any] = {
            "cwd": self.get_cwd_rel(),
            "params_input": params_input,
        }
        if path_resolved is not None:
            context["path_resolved"] = path_resolved
        if extra_context:
            context.update(extra_context)

        # 构建 stats
        stats: Dict[str, Any] = {"time_ms": time_ms}

        # 构建 payload（error 响应的 data 允许携带结构化信息）
        error_data: Dict[str, Any] = data or {}
        payload = {
            "status": ToolStatus.ERROR.value,
            "data": error_data,
            "text": message,
            "error": {
                "code": error_code.value,
                "message": message,
            },
            "stats": stats,
            "context": context,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_response(
            self,
            status: ToolStatus,
            data: Dict[str, Any],
            text: str,
            params_input: Dict[str, Any],
            time_ms: int,
            extra_stats: Optional[Dict[str, Any]] = None,
            path_resolved: Optional[str] = None,
            extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        内部方法：构建标准响应信封

        顶层字段严格限制为：status, data, text, stats, context
        （error 仅在 status="error" 时由 create_error_response 添加）
        """
        # 构建 context（必填字段）
        context: Dict[str, Any] = {
            "cwd": self.get_cwd_rel(),
            "params_input": params_input,
        }
        if path_resolved is not None:
            context["path_resolved"] = path_resolved
        if extra_context:
            context.update(extra_context)

        # 构建 stats（time_ms 必填）
        try:
            time_ms = int(time_ms)
        except Exception:
            time_ms = 0
        if status != ToolStatus.ERROR and time_ms <= 0:
            time_ms = 1
        stats: Dict[str, Any] = {"time_ms": time_ms}
        if extra_stats:
            stats.update(extra_stats)

        # 构建 payload
        payload = {
            "status": status.value,
            "data": data,
            "text": text,
            "stats": stats,
            "context": context,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------------------
    # 其他辅助方法
    # -------------------------------------------------------------------------

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证参数完整性"""
        required_params = [p.name for p in self.get_parameters() if p.required]
        return all(param in parameters for param in required_params)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [param for param in self.get_parameters()]
        }

    def __str__(self) -> str:
        return f"Tool(name={self.name})"

    def __repr__(self) -> str:
        return self.__str__()

    def to_openai_schema(self) -> Dict[str, Any]:
        """
        转换为OpenAI function calling schema 定义格式
        使工具能够被支持原生function calling的LLM调用
        :return:
        """
        def get_property_schema(params: List[ToolParameter]) -> Dict[str, Any]:
            properties = {}
            for param in params:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
            return properties

        return {
            "type": "function",
            "function":{
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": get_property_schema(self.get_parameters()),
                    "required": [param.name for param in self.get_parameters() if param.required],
                },
            }
        }
