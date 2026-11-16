from langgraph.types import interrupt

from app.state import AgentState
from app.observability import log_event


def human_approval_node(state: AgentState):
    """
    Pause the graph and ask the human to approve a database write operation.
    """

    query = state.get("sql_query", "")

    log_event(
        event="human_approval_requested",
        node="approval",
        sql_query=query,
    )

    approval = interrupt(
        {
            "type": "database_approval",
            "message": "A database write operation requires human approval.",
            "sql": query,
        }
    )

    if isinstance(approval, str):
        status = (
            "approved"
            if approval.strip().lower() in ("yes", "y", "approve", "approved")
            else "rejected"
        )
    elif isinstance(approval, dict):
        status = approval.get("approval_status", "rejected")
    else:
        status = "approved" if bool(approval) else "rejected"

    log_event(
        event="human_approval_resolved",
        node="approval",
        approval_status=status,
        raw_response=str(approval),
    )

    return {
        "approval_status": status,
    }