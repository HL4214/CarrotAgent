import logging
import os
from datetime import datetime
from pathlib import Path


class AgentLogger:
    def __init__(self, log_dir: str = "logs", name: str = "AgentTrace"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 1. 生成基于时间的唯一文件名 (例如: 20240520_143005_AgentTrace.log)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{timestamp}_{name}.log"
        # self.log_file = self.log_dir / f"{name}.log"

        # 2. 创建自定义 Logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加 Handler（防止在某些环境下日志翻倍）
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self):
        # 设置统一的日志格式
        # [时间] [级别] [文件名:行号] - 消息
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        # 控制台格式可以稍微精简一点
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

        # 3. 文件 Handler (记录所有 DEBUG 级别以上的详细信息)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)

        # 4. 控制台 Handler (通常设为 INFO 级别，保持界面整洁)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger


# 初始化一个全局实例方便直接调用
logger = AgentLogger().get_logger()