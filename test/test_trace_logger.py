from src.utils.trace_doubao import AgentTrace



def test_trace_doubao():
    test_dir = "./test_log"
    trace = AgentTrace(base_dir=str(test_dir))

    trace.record_user_input({"input": "Hello, world!"})
    trace.record_llm_interaction(
        prompt="Hello",
        response="Hi there!",
        token_usage={"total_tokens": 10}
    )
    trace.record_tool_call(
        tool_name="calculator",
        tool_params={"a": 1, "b": 2},
        tool_result={"sum": 3}
    )

    # 2. 执行导出
    trace.export_to_html()

test_trace_doubao()