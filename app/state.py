from typing import Annotated, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict


class AgentState(TypedDict):
    """The core state schema for the agent."""
    messages: Annotated[
        list[AnyMessage],   
        add_messages
    ]
    schema_context: NotRequired[str]
    sql_query: NotRequired[str]
    sql_result: NotRequired[str]
    error: NotRequired[str]
    retry_count: NotRequired[int]
    approval_status: NotRequired[str]


class AgentRuntime(TypedDict, total=False):
    """Runtime configurable variables passed into the agent."""
    thread_id: str
    db: Any


AgentConfiguration = AgentRuntime