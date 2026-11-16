from langchain_core.messages import AIMessage
from app.state import AgentState
from app.security.input_guard import validate_input
from app.observability import log_event


def input_guardrail_node(state: AgentState):

    messages = state.get("messages", [])

    if not messages:
        log_event(
            event="input_guardrail_rejected",
            node="input_guardrail",
            reason="no_user_input",
        )
        return {
            "error": "No user input provided.",
            "messages": [AIMessage(content="Error: No user input provided.")],
        }

    user_input = messages[-1].content

    is_valid, message = validate_input(user_input)

    log_event(
        event="input_guardrail_evaluated",
        node="input_guardrail",
        is_valid=is_valid,
        message=message,
    )

    if not is_valid:
        return {
            "error": message,
            "messages": [AIMessage(content=f"Request blocked by safety guardrail: {message}")],
        }

    return {
        "error": ""
    }