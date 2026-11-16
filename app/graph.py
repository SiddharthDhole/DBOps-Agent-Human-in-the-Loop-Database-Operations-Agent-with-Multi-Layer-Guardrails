import os

from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

from app.state import AgentState

from app.nodes import (
    agent_node,
    context_manager_node,
    retry_node,
    route_after_tool,
    sql_risk_router,
    human_approval_node,
    input_guardrail_node,
    output_guardrail_node,
)

from app.tools import tools


load_dotenv()


# ============================================================
# Graph
# ============================================================

builder = StateGraph(AgentState)


# ============================================================
# Nodes
# ============================================================

builder.add_node(
    "input_guardrail",
    input_guardrail_node,
)

builder.add_node(
    "context_manager",
    context_manager_node,
)

builder.add_node(
    "agent",
    agent_node,
)

builder.add_node(
    "sql_risk_router",
    sql_risk_router,
)

builder.add_node(
    "approval",
    human_approval_node,
)

builder.add_node(
    "tools",
    ToolNode(tools),
)

builder.add_node(
    "retry",
    retry_node,
)

builder.add_node(
    "output_guardrail",
    output_guardrail_node,
)


# ============================================================
# START -> Input Guardrail
# ============================================================

builder.add_edge(
    START,
    "input_guardrail",
)


# ============================================================
# Input Guardrail
# ============================================================

def route_after_input_guardrail(state: AgentState):

    if state.get("error"):
        return "blocked"

    return "allowed"


builder.add_conditional_edges(
    "input_guardrail",
    route_after_input_guardrail,
    {
        "allowed": "context_manager",
        "blocked": END,
    },
)


# ============================================================
# Context Manager -> Agent
# ============================================================

builder.add_edge(
    "context_manager",
    "agent",
)


# ============================================================
# Agent -> SQL Risk Router
# ============================================================

builder.add_conditional_edges(
    "agent",
    sql_risk_router,
    {
        # Safe SELECT query
        "execute": "tools",

        # INSERT / UPDATE / DELETE
        "approval": "approval",

        # Dangerous operation
        "blocked": END,

        # Agent has produced final answer
        "end": "output_guardrail",
    },
)


# ============================================================
# Human Approval
# ============================================================

def route_after_approval(state: AgentState):

    return state.get(
        "approval_status",
        "rejected",
    )


builder.add_conditional_edges(
    "approval",
    route_after_approval,
    {
        "approved": "tools",
        "rejected": END,
    },
)


# ============================================================
# Tools -> Agent / Retry / Output
# ============================================================

builder.add_conditional_edges(
    "tools",
    route_after_tool,
    {
        # Successful SQL execution
        # Go back to agent so it can analyze the result
        "agent": "agent",

        # SQL execution error
        "retry": "retry",

        # Final tool failure / max retry
        "finish": "output_guardrail",
    },
)


# ============================================================
# Retry -> Agent
# ============================================================

builder.add_edge(
    "retry",
    "agent",
)


# ============================================================
# Output Guardrail
# ============================================================

def route_after_output_guardrail(state: AgentState):

    if state.get("error"):
        return "blocked"

    return "safe"


builder.add_conditional_edges(
    "output_guardrail",
    route_after_output_guardrail,
    {
        "safe": END,
        "blocked": END,
    },
)


# ============================================================
# Checkpointer (PostgresSaver with MemorySaver fallback)
# ============================================================

def init_checkpointer():
    """
    Initialize checkpointer.
    Attempts PostgreSQL persistence if DB_URI is configured and reachable.
    Falls back gracefully to MemorySaver to prevent module import hang or crash.
    """
    db_uri = os.getenv("DB_URI")
    if db_uri:
        try:
            conn = Connection.connect(
                db_uri,
                autocommit=True,
                prepare_threshold=0,
                row_factory=dict_row,
                connect_timeout=3,
            )
            checkpointer = PostgresSaver(conn)
            checkpointer.setup()
            return checkpointer
        except Exception as exc:
            print(f"[WARN] PostgreSQL Checkpointer connection failed ({exc}). Falling back to MemorySaver.")
    return MemorySaver()


checkpointer = init_checkpointer()


# ============================================================
# Compile
# ============================================================

graph = builder.compile(
    checkpointer=checkpointer,
)