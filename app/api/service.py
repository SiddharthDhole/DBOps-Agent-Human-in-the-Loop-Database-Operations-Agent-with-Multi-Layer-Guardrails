import asyncio
import uuid
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.api.callbacks import StreamingCallbackHandler
from app.db.connection import db
from app.graph import graph


def run_agent_sync(question: str, thread_id: str) -> dict[str, Any]:
    """
    Execute the agent synchronously for REST endpoints.
    Returns status, answer, and whether human approval is pending.
    """
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "db": db,
        }
    }

    result = graph.invoke(
        {"messages": [HumanMessage(content=question)]},
        config=config,
    )

    # Check for Human-In-The-Loop Interrupt
    if result.get("__interrupt__"):
        for item in result["__interrupt__"]:
            val = item.value
            sql = val.get("sql") if isinstance(val, dict) else ""
            msg = val.get("message") if isinstance(val, dict) else str(val)
            return {
                "approval_required": True,
                "pending_sql": sql,
                "message": msg,
                "answer": f"APPROVAL REQUIRED: {msg}\nProposed SQL:\n{sql}",
            }

    if result.get("approval_status") == "rejected":
        return {
            "approval_required": False,
            "answer": "Operation cancelled: Database write was rejected by user.",
        }

    # Extract final text message
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
            return {
                "approval_required": False,
                "answer": msg.content.strip(),
            }

    return {
        "approval_required": False,
        "answer": "Operation completed.",
    }


def resume_agent_sync(thread_id: str, decision: str) -> dict[str, Any]:
    """Resume an interrupted agent thread with approval decision."""
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "db": db,
        }
    }

    result = graph.invoke(
        Command(resume=decision),
        config=config,
    )

    if result.get("approval_status") == "rejected":
        return {
            "status": "rejected",
            "answer": "Operation cancelled: Database write was rejected.",
        }

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
            return {
                "status": "completed",
                "answer": msg.content.strip(),
            }

    return {
        "status": "completed",
        "answer": "Operation completed.",
    }


async def stream_agent_session(
    question: str,
    thread_id: str,
    event_queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
):
    """
    Stream agent execution in a worker thread, pushing real-time LLM tokens,
    tool execution logs, and node status events into the event_queue.
    """
    callback = StreamingCallbackHandler(event_queue, loop=loop)
    config: RunnableConfig = {
        "callbacks": [callback],
        "configurable": {
            "thread_id": thread_id,
            "db": db,
        },
    }

    def _sync_worker():
        try:
            # Emit pipeline start
            asyncio.run_coroutine_threadsafe(
                event_queue.put({
                    "type": "pipeline_start",
                    "question": question,
                    "thread_id": thread_id,
                }),
                loop,
            )

            # Stream through graph updates
            for update in graph.stream(
                {"messages": [HumanMessage(content=question)]},
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_state in update.items():
                    # Handle node update events
                    msg = f"Completed node: {node_name}"
                    extra = {}
                    if node_name == "input_guardrail":
                        msg = "Input Guardrail: Query passed security checks."
                    elif node_name == "context_manager":
                        msg = "Context Manager: Retrieved database schema context."
                    elif node_name == "sql_risk_router":
                        msg = "SQL Risk Router: Evaluated query permissions."
                    elif node_name == "retry":
                        msg = f"Retry Node: Retrying query (attempt {node_state.get('retry_count', 1)})..."
                    elif node_name == "output_guardrail":
                        msg = "Output Guardrail: Validated response safety."

                    asyncio.run_coroutine_threadsafe(
                        event_queue.put({
                            "type": "node_update",
                            "node": node_name,
                            "message": msg,
                            **extra,
                        }),
                        loop,
                    )

            # Check if paused on interrupt
            state = graph.get_state(config)
            if state.tasks:
                for task in state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        for inter in task.interrupts:
                            val = inter.value if hasattr(inter, "value") else str(inter)
                            sql = val.get("sql") if isinstance(val, dict) else ""
                            msg = val.get("message") if isinstance(val, dict) else str(val)
                            asyncio.run_coroutine_threadsafe(
                                event_queue.put({
                                    "type": "approval_required",
                                    "message": msg,
                                    "sql": sql,
                                }),
                                loop,
                            )
                            return

            # Extract final message from state
            final_content = "Operation completed."
            if state.values and "messages" in state.values:
                for m in reversed(state.values["messages"]):
                    if hasattr(m, "content") and isinstance(m.content, str) and m.content.strip():
                        final_content = m.content.strip()
                        break

            asyncio.run_coroutine_threadsafe(
                event_queue.put({
                    "type": "final_answer",
                    "answer": final_content,
                }),
                loop,
            )

        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                event_queue.put({
                    "type": "error",
                    "error": str(exc),
                }),
                loop,
            )
        finally:
            asyncio.run_coroutine_threadsafe(
                event_queue.put({"type": "stream_end"}),
                loop,
            )

    # Run sync graph stream in executor thread
    await asyncio.to_thread(_sync_worker)


async def resume_agent_stream(
    decision: str,
    thread_id: str,
    event_queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
):
    """Resume stream after human approval or rejection."""
    callback = StreamingCallbackHandler(event_queue, loop=loop)
    config: RunnableConfig = {
        "callbacks": [callback],
        "configurable": {
            "thread_id": thread_id,
            "db": db,
        },
    }

    def _sync_worker():
        try:
            asyncio.run_coroutine_threadsafe(
                event_queue.put({
                    "type": "approval_resolved",
                    "decision": decision,
                    "message": f"Resuming execution with decision: {decision}",
                }),
                loop,
            )

            for update in graph.stream(
                Command(resume=decision),
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_state in update.items():
                    asyncio.run_coroutine_threadsafe(
                        event_queue.put({
                            "type": "node_update",
                            "node": node_name,
                            "message": f"Completed node: {node_name}",
                        }),
                        loop,
                    )

            state = graph.get_state(config)
            final_content = "Operation completed."
            if state.values and state.values.get("approval_status") == "rejected":
                final_content = "Operation cancelled: Database write operation was rejected."
            elif state.values and "messages" in state.values:
                for m in reversed(state.values["messages"]):
                    if hasattr(m, "content") and isinstance(m.content, str) and m.content.strip():
                        final_content = m.content.strip()
                        break

            asyncio.run_coroutine_threadsafe(
                event_queue.put({
                    "type": "final_answer",
                    "answer": final_content,
                }),
                loop,
            )
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                event_queue.put({
                    "type": "error",
                    "error": str(exc),
                }),
                loop,
            )
        finally:
            asyncio.run_coroutine_threadsafe(
                event_queue.put({"type": "stream_end"}),
                loop,
            )

    await asyncio.to_thread(_sync_worker)
