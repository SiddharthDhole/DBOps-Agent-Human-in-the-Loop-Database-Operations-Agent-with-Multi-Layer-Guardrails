from app.state import AgentState
from app.observability import log_event


MAX_RETRIES = 3


def retry_node(state: AgentState):
    new_retry_count = state.get("retry_count", 0) + 1

    log_event(
        event="retry_node_invoked",
        node="retry",
        retry_count=new_retry_count,
        max_retries=MAX_RETRIES,
    )

    return {
        "retry_count": new_retry_count
    }


def route_after_tool(state: AgentState) -> str:

    messages = state.get("messages", [])

    if not messages:
        log_event(
            event="route_after_tool",
            node="route_after_tool",
            route="agent",
            reason="no_messages",
        )
        return "agent"

    last_message = messages[-1]

    content = getattr(
        last_message,
        "content",
        ""
    )

    # SQL execution failed
    if "SQL_EXECUTION_ERROR" in content:

        retry_count = state.get(
            "retry_count",
            0
        )

        if retry_count < MAX_RETRIES:
            log_event(
                event="route_after_tool",
                node="route_after_tool",
                route="retry",
                retry_count=retry_count,
                reason="sql_execution_error",
            )
            return "retry"

        log_event(
            event="route_after_tool",
            node="route_after_tool",
            route="finish",
            retry_count=retry_count,
            reason="max_retries_exceeded",
        )
        return "finish"

    # SQL was intentionally blocked
    if "SQL_BLOCKED" in content:
        log_event(
            event="route_after_tool",
            node="route_after_tool",
            route="finish",
            reason="sql_blocked",
        )
        return "finish"

    # Tool succeeded
    log_event(
        event="route_after_tool",
        node="route_after_tool",
        route="agent",
        reason="tool_success",
    )
    return "agent"