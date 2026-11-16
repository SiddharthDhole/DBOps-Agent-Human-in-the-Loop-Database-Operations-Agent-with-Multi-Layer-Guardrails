import uuid
from typing import Any, Optional
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from deepeval.test_case import ToolCall

from app.db.connection import db
from app.graph import graph


def invoke_agent_for_eval(
    question: str,
    auto_approve_write: bool = False,
    thread_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Invokes the DBOps graph in an evaluation-friendly mode.
    Returns:
        {
            "final_answer": str,
            "tool_calls": list[ToolCall],
            "sql_query": Optional[str],
            "sql_result": Optional[str],
            "hitl_interrupted": bool,
            "approval_message": Optional[str],
            "state": dict
        }
    """
    tid = thread_id or f"eval_{uuid.uuid4().hex[:8]}"
    config: RunnableConfig = {
        "configurable": {
            "thread_id": tid,
            "db": db,
        }
    }

    result = graph.invoke(
        {"messages": [HumanMessage(content=question)]},
        config=config,
    )

    hitl_interrupted = False
    approval_message = None

    # Handle interrupts (human in the loop for writes)
    if result.get("__interrupt__"):
        hitl_interrupted = True
        interrupt_item = result["__interrupt__"][0]
        val = interrupt_item.value
        if isinstance(val, dict):
            approval_message = val.get("message")
        else:
            approval_message = str(val)

        if auto_approve_write:
            decision = "approved"
        else:
            decision = "rejected"

        result = graph.invoke(
            Command(resume=decision),
            config=config,
        )

    # Extract all tool calls from trajectory
    collected_tool_calls: list[ToolCall] = []
    messages = result.get("messages", [])
    for msg in messages:
        calls = getattr(msg, "tool_calls", None)
        if calls:
            for tc in calls:
                collected_tool_calls.append(
                    ToolCall(
                        name=tc.get("name", ""),
                        input_parameters=tc.get("args", {}),
                    )
                )

    # Determine final answer text
    final_answer = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
            final_answer = msg.content.strip()
            break

    if not final_answer:
        final_answer = "Operation completed."

    return {
        "final_answer": final_answer,
        "tool_calls": collected_tool_calls,
        "sql_query": result.get("sql_query"),
        "sql_result": result.get("sql_result"),
        "hitl_interrupted": hitl_interrupted,
        "approval_message": approval_message,
        "state": result,
    }
