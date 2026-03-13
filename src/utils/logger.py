import logging
import sys
from typing import List, Dict, Optional
from pathlib import Path


class CarrotLogger:
    """
    CarrotAgent的日志库，用于记录运行过程中的错误、日志打印和LLM对话消息等。
    支持标准日志级别，并提供专门的方法记录LLM消息。
    """

    def __init__(self,
                 name: str = "CarrotAgent",
                 level: int = logging.INFO,
                 log_file: Optional[str] = None,
                 console: bool = True):
        """
        初始化日志器

        :param name: 日志器名称
        :param level: 日志级别
        :param log_file: 日志文件路径，如果提供则写入文件
        :param console: 是否输出到控制台
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # 避免重复添加handler
        if self.logger.handlers:
            return

        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 控制台handler
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # 文件handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)

    def info(self, message: str):
        """记录信息"""
        self.logger.info(message)

    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(message)

    def error(self, message: str, exc_info: Optional[Exception] = None):
        """记录错误"""
        if exc_info:
            self.logger.error(message, exc_info=exc_info)
        else:
            self.logger.error(message)

    def critical(self, message: str):
        """记录严重错误"""
        self.logger.critical(message)

    def log_llm_message(self, messages: List[Dict[str, str]], response: Optional[str] = None):
        """
        记录LLM对话消息

        :param messages: 输入消息列表
        :param response: LLM响应内容
        """
        log_message = "LLM对话:\n"
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            log_message += f"  {role}: {content}\n"
        if response:
            log_message += f"  response: {response}\n"
        self.logger.info(log_message.strip())

    def log_llm_stream(self, messages: List[Dict[str, str]], stream_chunks: List[str]):
        """
        记录LLM流式响应

        :param messages: 输入消息列表
        :param stream_chunks: 流式响应的片段列表
        """
        log_message = "LLM流式对话:\n"
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            log_message += f"  {role}: {content}\n"
        full_response = ''.join(stream_chunks)
        log_message += f"  response: {full_response}\n"
        self.logger.info(log_message.strip())

    def log_exception(self, exc: Exception, message: Optional[str] = None):
        """
        记录异常

        :param exc: 异常对象
        :param message: 额外消息
        """
        if message:
            self.logger.error(f"{message}: {str(exc)}", exc_info=exc)
        else:
            self.logger.error(f"异常: {str(exc)}", exc_info=exc)


# 全局日志器实例
default_logger = CarrotLogger()


def get_logger(name: str = "CarrotAgent",
               log_file: str = None) -> CarrotLogger:
    """
    获取日志器实例

    :param name: 日志器名称
    :return: CarrotLogger实例
    """
    return CarrotLogger(name, log_file=log_file)
