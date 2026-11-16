from langchain_core.messages import AIMessage
from app.state import AgentState
from app.security.output_guard import validate_output
from app.observability import log_event


def output_guardrail_node(state: AgentState):

    messages = state.get("messages", [])

    if not messages:
        log_event(
            event="output_guardrail_rejected",
            node="output_guardrail",
            reason="no_agent_response",
        )
        return {
            "error": "No agent response found.",
            "messages": [AIMessage(content="Error: No agent response found.")],
        }

    final_message = messages[-1]

    output = getattr(
        final_message,
        "content",
        ""
    )

    if not isinstance(output, str):
        output = str(output)

    is_valid, message = validate_output(output)

    log_event(
        event="output_guardrail_evaluated",
        node="output_guardrail",
        is_valid=is_valid,
        message=message,
        output_length=len(output),
    )

    if not is_valid:
        return {
            "error": message,
            "messages": [AIMessage(content=f"Response blocked by safety guardrail: {message}")],
        }

    return {
        "error": ""
    }