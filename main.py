import uuid
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.db.connection import db
from app.graph import graph


def run_agent(
    question: str,
    config: Optional[RunnableConfig] = None,
) -> str:
    if config is None:
        config = {
            "configurable": {
                "thread_id": str(uuid.uuid4()),
                "db": db,
            }
        }

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=question
                )
            ]
        },
        config=config,
    )

    # ----------------------------------------------------
    # Human-In-The-Loop (HITL) Interrupt Handling
    # ----------------------------------------------------
    while result.get("__interrupt__"):
        for interrupt_item in result["__interrupt__"]:
            interrupt_data = interrupt_item.value

            print("\n" + "=" * 55)
            print("🚨 HUMAN APPROVAL REQUIRED")
            print("=" * 55)

            if isinstance(interrupt_data, dict):
                msg = interrupt_data.get(
                    "message",
                    "A database write operation requires human approval.",
                )
                sql = interrupt_data.get("sql")
                print(f"Notice : {msg}")
                if sql:
                    print(f"\nProposed SQL:\n  {sql}")
            else:
                print(f"Notice : {interrupt_data}")

            print("=" * 55)

            while True:
                choice = input("\nDo you approve this operation? (yes/no): ").strip().lower()
                if choice in ("yes", "y", "approve"):
                    decision = "approved"
                    break
                elif choice in ("no", "n", "reject"):
                    decision = "rejected"
                    break
                else:
                    print("Please enter 'yes' to approve or 'no' to reject.")

            print(f"\nResuming execution ({decision})...\n")

            result = graph.invoke(
                Command(resume=decision),
                config=config,
            )

    # ----------------------------------------------------
    # Format Final Agent Response
    # ----------------------------------------------------
    if result.get("approval_status") == "rejected":
        return "Operation cancelled: Database write was rejected by the user."

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
            return msg.content.strip()

    return "Operation completed."


if __name__ == "__main__":
    session_thread_id = str(uuid.uuid4())
    runtime_config: RunnableConfig = {
        "configurable": {
            "thread_id": session_thread_id,
            "db": db,
        }
    }

    print("\nDBOps Agent")
    print("Type 'exit' to quit.\n")

    while True:

        question = input("You: ")

        if question.lower() == "exit":
            break

        try:

            answer = run_agent(question, config=runtime_config)

            print("\nAgent:")
            print(answer)
            print()

        except Exception as exc:

            print(
                f"\nAgent Error: {exc}\n"
            )
