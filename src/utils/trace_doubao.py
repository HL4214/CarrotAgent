import threading
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
import uuid
import time
import json
from pathlib import Path
from typing import Any


class StepType(Enum):
    USER_INPUT = "user_input"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    ERROR = "error"
    SYSTEM = "system"


class StepStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class TraceStep:
    step_type: StepType
    content: dict
    trace_id: str
    parent_id: str = None
    status: StepStatus = StepStatus.SUCCESS
    metadata: dict = field(default_factory=dict)
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        d = asdict(self)
        d.update({"step_type": self.step_type.value, "status": self.status.value})
        return d


# 核心Trace记录类（增强版，支持直接导出HTML）
class AgentTrace:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, base_dir: str = "logs"):
        if getattr(self, "_initialized", False): return

        self.start_time = datetime.now()
        self.trace_id = str(uuid.uuid4())
        # 自动生成文件名: trace_20231027_1030_uuid.json
        time_str = datetime.now().strftime("%Y%m%d_%H%M")
        self.file_path = Path(base_dir) / f"trace_{time_str}_{self.trace_id[:8]}.json"
        self.html_file_path = Path(base_dir) / f"trace_{time_str}_{self.trace_id[:8]}.html"
        self.steps = []
        self._initialized = True

    def _save_to_json(self, step: TraceStep):
        """延迟创建文件并追加内容"""
        with self._lock:
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # 如果文件不存在，初始化结构；否则读取
            if not self.file_path.exists():
                data = {"trace_id": self.trace_id, "start_time": datetime.now().isoformat(), "steps": []}
            else:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            data["steps"].append(step.to_dict())

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def add_step(self, step_type: StepType, content: dict, **kwargs):
        step = TraceStep(trace_id=self.trace_id, step_type=step_type, content=content, **kwargs)
        self.steps.append(step)
        self._save_to_json(step)
        return step.step_id

    # ========== 快捷记录方法 ==========
    def record_user_input(self, user_input: Any, metadata: dict = {}):
        """记录用户输入"""
        if isinstance(user_input, dict):
            content = user_input
        else:
            content = {"input": user_input}

        return self.add_step(
            step_type=StepType.USER_INPUT,
            content=content,
            metadata=metadata
        )

    def record_system(self, content: Any, metadata: dict = {}):
        """记录系统输入"""
        if not isinstance(content, str):
            content = str(content)

        return self.add_step(
            step_type=StepType.SYSTEM,
            content={"system": content},
            metadata=metadata
        )

    def record_llm_interaction(self, prompt: str, response: str, token_usage: dict = None, metadata: dict = {}):
        """记录LLM调用（包含耗时和token）"""
        start_time = time.time()
        # 记录LLM请求
        req_step_id = self.add_step(
            step_type=StepType.LLM_REQUEST,
            content={"prompt": prompt},
            metadata=metadata
        )
        # 模拟耗时（实际场景替换为真实LLM调用）
        time.sleep(0.01)
        end_time = time.time()

        # 记录LLM响应
        resp_metadata = metadata or {}
        if token_usage:
            resp_metadata["token_usage"] = token_usage
        resp_metadata["elapsed_time"] = round(end_time - start_time, 3)

        self.add_step(
            step_type=StepType.LLM_RESPONSE,
            content={"response": response},
            parent_id=req_step_id,
            metadata=resp_metadata
        )
        return req_step_id

    def record_tool_call(self, tool_name: str, tool_params: dict, tool_result: dict,
                         success: bool = True, metadata: dict = {}):
        """记录工具调用"""
        call_step_id = self.add_step(
            step_type=StepType.TOOL_CALL,
            content={"tool_name": tool_name, "params": tool_params},
            metadata=metadata,
            status=StepStatus.SUCCESS if success else StepStatus.FAILED
        )
        # 补充工具响应
        self.add_step(
            step_type=StepType.TOOL_RESPONSE,
            content={"tool_name": tool_name, "result": tool_result},
            parent_id=call_step_id,
            metadata=metadata,
            status=StepStatus.SUCCESS if success else StepStatus.FAILED
        )
        return call_step_id

    def record_error(self, error_type: str, error_msg: str, stack_trace: str, parent_id: str = None):
        """记录错误信息"""
        return self.add_step(
            step_type=StepType.ERROR,
            content={
                "error_type": error_type,
                "error_msg": error_msg,
                "stack_trace": stack_trace
            },
            parent_id=parent_id,
            status=StepStatus.FAILED,
            metadata={"tag": ["error", "debug"]}
        )

    # ========== 核心功能：导出可视化HTML ==========
    def export_to_html(self):
        """
        将Trace记录导出为单个HTML文件（可直接打开，无需依赖外部资源）
        :param file_path: 保存路径，默认 agent_trace_report.html
        """
        # 1. 构造前端渲染所需的结构化数据
        type_mapping = {
            StepType.USER_INPUT: {"name": "用户输入", "color": "#4285F4"},
            StepType.LLM_REQUEST: {"name": "LLM请求", "color": "#F4B400"},
            StepType.LLM_RESPONSE: {"name": "LLM响应", "color": "#0F9D58"},
            StepType.TOOL_CALL: {"name": "工具调用", "color": "#9C27B0"},
            StepType.TOOL_RESPONSE: {"name": "工具响应", "color": "#FF9800"},
            StepType.SYSTEM: {"name": "系统输入", "color": "#00ACC1"},
            StepType.ERROR: {"name": "错误", "color": "#DB4437"}
        }

        # 处理步骤数据
        steps_data = []
        for step in self.steps:
            # 简化展示内容（截断长文本）
            if step.step_type == StepType.USER_INPUT:
                display_content = step.content.get("input", "")
            elif step.step_type == StepType.LLM_REQUEST:
                prompt = step.content.get("prompt", "")
                display_content = prompt[:200] + "..." if len(prompt) > 200 else prompt
            elif step.step_type == StepType.LLM_RESPONSE:
                response = step.content.get("response", "")
                display_content = response[:200] + "..." if len(response) > 200 else response
            elif step.step_type == StepType.TOOL_CALL:
                display_content = f"工具：{step.content.get('tool_name')} | 参数：{json.dumps(step.content.get('params', {}), ensure_ascii=False)}"
            elif step.step_type == StepType.TOOL_RESPONSE:
                result = json.dumps(step.content.get('result', {}), ensure_ascii=False)
                display_content = f"工具：{step.content.get('tool_name')} | 结果：{result[:200]}..." if len(
                    result) > 200 else f"工具：{step.content.get('tool_name')} | 结果：{result}"
            elif step.step_type == StepType.ERROR:
                display_content = f"错误类型：{step.content.get('error_type')} | 信息：{step.content.get('error_msg')}"
            else:
                display_content = json.dumps(step.content, ensure_ascii=False)[:200] + "..." if len(
                    str(step.content)) > 200 else json.dumps(step.content, ensure_ascii=False)

            steps_data.append({
                "step_id": step.step_id,
                "parent_id": step.parent_id,
                "type": step.step_type.value,
                "type_name": type_mapping[step.step_type]["name"],
                "type_color": type_mapping[step.step_type]["color"],
                "timestamp": step.timestamp.format(),
                "display_content": display_content,
                "raw_content": step.content,
                "metadata": step.metadata,
                "status": step.status.value,
                "elapsed_time": step.metadata.get("elapsed_time", 0)
            })

        # 2. 构造HTML模板（内嵌所有数据和样式、逻辑）
        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Trace 可视化报告</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: "Microsoft YaHei", Arial, sans-serif;
        }
        body {
            background-color: #f5f7fa;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }
        .header {
            border-bottom: 2px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 25px;
        }
        .header h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header h1 span {
            font-size: 14px;
            color: #666;
            background: #f0f0f0;
            padding: 4px 10px;
            border-radius: 4px;
            margin-left: 10px;
        }
        .header-info {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            color: #666;
            font-size: 14px;
        }
        .filter-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            align-items: center;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 8px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }
        .filter-btn.active {
            background: #4285F4;
            color: white;
            border-color: #4285F4;
        }
        .filter-btn:hover:not(.active) {
            border-color: #4285F4;
            color: #4285F4;
        }
        .step-list {
            margin-left: 5px;
        }
        .step-item {
            margin-bottom: 20px;
            border-left: 3px solid #ddd;
            padding-left: 20px;
            position: relative;
        }
        .step-item:before {
            content: "";
            position: absolute;
            left: -7px;
            top: 20px;
            width: 11px;
            height: 11px;
            border-radius: 50%;
            background: #ddd;
            box-shadow: 0 0 0 2px white;
        }
        .step-item.failed {
            border-left-color: #DB4437;
        }
        .step-item.failed:before {
            background: #DB4437;
        }
        .step-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
            cursor: pointer;
        }
        .step-type {
            padding: 4px 10px;
            border-radius: 6px;
            color: white;
            font-size: 13px;
            font-weight: bold;
        }
        .step-time {
            color: #999;
            font-size: 13px;
        }
        .step-status {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }
        .status-success {
            background: #e8f5e9;
            color: #2e7d32;
        }
        .status-failed {
            background: #ffebee;
            color: #c62828;
        }
        .status-processing {
            background: #fff8e1;
            color: #f57f17;
        }
        .step-elapsed {
            color: #666;
            font-size: 13px;
            margin-left: auto;
            background: #f0f0f0;
            padding: 3px 8px;
            border-radius: 4px;
        }
        .step-content {
            background: #f9f9f9;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 10px;
            font-size: 14px;
            line-height: 1.6;
            color: #333;
        }
        .step-details {
            font-size: 12px;
            color: #666;
            background: #f5f5f5;
            padding: 10px;
            border-radius: 6px;
            display: none;
            margin-bottom: 5px;
        }
        .step-details pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.5;
        }
        .expand-btn {
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: #eee;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            cursor: pointer;
            transition: transform 0.2s;
            user-select: none;
        }
        .expand-btn.open {
            transform: rotate(90deg);
            background: #4285F4;
            color: white;
        }
        .nested-steps {
            margin-left: 25px;
            margin-top: 15px;
        }
        .empty-tip {
            text-align: center;
            color: #999;
            font-size: 16px;
            padding: 50px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部信息 -->
        <div class="header">
            <h1>Agent 执行轨迹可视化 <span>Trace ID: {trace_id}</span></h1>
            <div class="header-info">
                <div>总步骤数: <strong>{total_steps}</strong></div>
                <div>启动时间: <strong>{start_time}</strong></div>
                <div>结束时间: <strong>{end_time}</strong></div>
                <div>失败步骤数: <strong>{failed_steps}</strong></div>
            </div>
        </div>

        <!-- 筛选栏 -->
        <div class="filter-bar">
            <button class="filter-btn active" data-filter="all">全部步骤</button>
            <button class="filter-btn" data-filter="user_input">用户输入</button>
            <button class="filter-btn" data-filter="llm_request,llm_response">LLM交互</button>
            <button class="filter-btn" data-filter="tool_call,tool_response">工具调用</button>
            <button class="filter-btn" data-filter="agent_decision">Agent决策</button>
            <button class="filter-btn" data-filter="error">错误信息</button>
        </div>

        <!-- 步骤列表 -->
        <div id="stepContainer" class="step-list">
            <!-- 步骤内容由JS动态生成 -->
        </div>
    </div>

    <script>
        // 内嵌的Trace数据
        const traceData = {trace_data};

        // 初始化页面
        document.addEventListener('DOMContentLoaded', function() {
            renderSteps(traceData.steps);
            bindFilterEvents();
        });

        // 渲染步骤列表（支持嵌套）
        function renderSteps(steps) {
            const container = document.getElementById('stepContainer');
            container.innerHTML = '';

            // 按时间排序
            const sortedSteps = [...steps].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

            if (sortedSteps.length === 0) {
                container.innerHTML = '<div class="empty-tip">暂无Trace记录</div>';
                return;
            }

            // 先渲染顶级步骤（无parent_id）
            const topLevelSteps = sortedSteps.filter(step => !step.parent_id);
            topLevelSteps.forEach(step => {
                container.appendChild(createStepElement(step, sortedSteps));
            });
        }

        // 创建单个步骤元素
        function createStepElement(step, allSteps) {
            const stepDiv = document.createElement('div');
            stepDiv.className = `step-item ${step.status === 'failed' ? 'failed' : ''}`;
            stepDiv.dataset.type = step.type;

            // 步骤头部
            const headerDiv = document.createElement('div');
            headerDiv.className = 'step-header';

            // 展开/收起按钮
            const expandBtn = document.createElement('div');
            expandBtn.className = 'expand-btn';
            expandBtn.textContent = '▶';
            expandBtn.onclick = function(e) {
                e.stopPropagation();
                const details = stepDiv.querySelector('.step-details');
                const nestedSteps = stepDiv.querySelector('.nested-steps');
                expandBtn.classList.toggle('open');
                details.style.display = expandBtn.classList.contains('open') ? 'block' : 'none';
                if (nestedSteps) {
                    nestedSteps.style.display = expandBtn.classList.contains('open') ? 'block' : 'none';
                }
            };

            // 步骤类型标签
            const typeSpan = document.createElement('span');
            typeSpan.className = 'step-type';
            typeSpan.style.backgroundColor = step.type_color;
            typeSpan.textContent = step.type_name;

            // 时间
            const timeSpan = document.createElement('span');
            timeSpan.className = 'step-time';
            timeSpan.textContent = formatTime(step.timestamp);

            // 状态
            const statusSpan = document.createElement('span');
            statusSpan.className = `step-status status-${step.status}`;
            statusSpan.textContent = step.status === 'success' ? '成功' : step.status === 'failed' ? '失败' : '处理中';

            // 耗时
            const elapsedSpan = document.createElement('span');
            elapsedSpan.className = 'step-elapsed';
            elapsedSpan.textContent = step.elapsed_time ? `耗时: ${step.elapsed_time}s` : '耗时: --';

            // 组装头部
            headerDiv.appendChild(expandBtn);
            headerDiv.appendChild(typeSpan);
            headerDiv.appendChild(timeSpan);
            headerDiv.appendChild(statusSpan);
            headerDiv.appendChild(elapsedSpan);

            // 步骤内容
            const contentDiv = document.createElement('div');
            contentDiv.className = 'step-content';
            contentDiv.textContent = step.display_content;

            // 步骤详情（原始数据）
            const detailsDiv = document.createElement('div');
            detailsDiv.className = 'step-details';
            const rawData = {
                原始内容: step.raw_content,
                元数据: step.metadata,
                步骤ID: step.step_id,
                父步骤ID: step.parent_id || '无'
            };
            detailsDiv.innerHTML = `<pre>${JSON.stringify(rawData, null, 2)}</pre>`;

            // 组装步骤元素
            stepDiv.appendChild(headerDiv);
            stepDiv.appendChild(contentDiv);
            stepDiv.appendChild(detailsDiv);

            // 渲染嵌套步骤
            const nestedSteps = allSteps.filter(s => s.parent_id === step.step_id);
            if (nestedSteps.length > 0) {
                const nestedDiv = document.createElement('div');
                nestedDiv.className = 'nested-steps';
                nestedDiv.style.display = 'none';
                nestedSteps.forEach(nestedStep => {
                    nestedDiv.appendChild(createStepElement(nestedStep, allSteps));
                });
                stepDiv.appendChild(nestedDiv);
            }

            // 点击头部展开/收起
            headerDiv.addEventListener('click', function() {
                expandBtn.click();
            });

            return stepDiv;
        }

        // 绑定筛选事件
        function bindFilterEvents() {
            const filterBtns = document.querySelectorAll('.filter-btn');
            filterBtns.forEach(btn => {
                btn.addEventListener('click', function() {
                    // 切换激活状态
                    filterBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');

                    // 筛选步骤
                    const filterType = this.dataset.filter;
                    const allSteps = document.querySelectorAll('.step-item');
                    allSteps.forEach(step => {
                        if (filterType === 'all') {
                            step.style.display = 'block';
                        } else {
                            const types = filterType.split(',');
                            step.style.display = types.includes(step.dataset.type) ? 'block' : 'none';
                        }
                    });
                });
            });
        }

        // 格式化时间
        function formatTime(isoTime) {
            const date = new Date(isoTime);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                fractionalSecondDigits: 3
            });
        }
    </script>
</body>
</html>
        """

        # 3. 填充模板变量
        end_time = max(step.timestamp for step in self.steps).format() if self.steps else datetime.now().isoformat()
        failed_steps = len([s for s in self.steps if s.status == StepStatus.FAILED])

        # 替换模板中的占位符
        html_content = html_template.format(
            trace_id=self.trace_id,
            total_steps=len(self.steps),
            start_time=self.start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            end_time=datetime.fromisoformat(end_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            failed_steps=failed_steps,
            trace_data=json.dumps({
                "trace_id": self.trace_id,
                "steps": steps_data
            }, ensure_ascii=False)
        )

        file_path = self.html_file_path
        # 4. 保存为HTML文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"✅ Trace可视化报告已生成：{file_path}")
        return file_path


def create_trace_logger(trace_dir: str = "memory/traces") -> AgentTrace:
    """
    工厂函数：创建 TraceLogger 实例
    """
    return AgentTrace(base_dir=trace_dir)
