from app.state import AgentState
from app.context.schema_context import (
    select_relevant_tables,
    build_schema_context,
)
from app.observability import log_event


def context_manager_node(state: AgentState):

    question = state["messages"][-1].content

    log_event(
        event="context_selection_started",
        node="context_manager",
        question=question,
    )

    tables = select_relevant_tables(
        question
    )

    schema_context = build_schema_context(
        tables
    )

    log_event(
        event="context_selection_completed",
        node="context_manager",
        tables=",".join(tables) if tables else "none",
        table_count=len(tables),
    )

    return {
        "schema_context": schema_context
    }