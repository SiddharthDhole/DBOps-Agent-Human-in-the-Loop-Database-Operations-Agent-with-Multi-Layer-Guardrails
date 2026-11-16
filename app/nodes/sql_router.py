from app.security.sql_policy import classify_sql
from app.observability import log_event


def sql_risk_router(state) -> str:
    """
    Route based on tool call risk:
    - 'end'      : No tool calls made (LLM answered directly)
    - 'execute'  : Safe read operations (SELECT, schema)
    - 'approval' : Sensitive write operations (INSERT, UPDATE, DELETE)
    - 'blocked'  : Prohibited statements (DROP, ALTER, syntax errors)
    """
    messages = state.get("messages", [])

    if not messages:
        log_event(
            event="sql_routing_skipped",
            node="sql_router",
            reason="no_messages",
            route="end",
        )
        return "end"

    last_message = messages[-1]

    tool_calls = getattr(
        last_message,
        "tool_calls",
        []
    )

    if not tool_calls:
        log_event(
            event="sql_routing_skipped",
            node="sql_router",
            reason="no_tool_calls",
            route="end",
        )
        return "end"

    for tool_call in tool_calls:

        tool_name = tool_call.get("name")

        if tool_name == "get_database_schema":
            log_event(
                event="sql_routing_decided",
                node="sql_router",
                tool=tool_name,
                policy="read",
                route="execute",
            )
            return "execute"

        if tool_name == "execute_sql":
            query = tool_call.get("args", {}).get("query", "")
            policy = classify_sql(query)

            if policy == "read":
                route = "execute"
            elif policy == "write":
                route = "approval"
            else:
                route = "blocked"

            log_event(
                event="sql_routing_decided",
                node="sql_router",
                tool=tool_name,
                policy=policy,
                route=route,
                query=query.replace("\n", " "),
            )

            return route

    log_event(
        event="sql_routing_default",
        node="sql_router",
        route="execute",
    )
    return "execute"