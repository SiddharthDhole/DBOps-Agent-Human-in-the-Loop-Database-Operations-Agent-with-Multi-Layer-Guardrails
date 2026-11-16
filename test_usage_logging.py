import os
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from app.graph import graph
from app.observability import llm_usage_tracker

load_dotenv()

def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding))

safe_print("\n==================================================")
safe_print("TESTING MULTI-STEP AGENT INVOCATION (SQL TOOL)")
safe_print("==================================================")

llm_usage_tracker.reset()

config = {"configurable": {"thread_id": "test_sql_session_202"}}

result = graph.invoke(
    {
        "messages": [HumanMessage(content="How many customers are in the database?")],
        "sql_query": None,
        "sql_result": None,
        "error": None,
        "retry_count": 0,
        "schema_context": None,
    },
    config=config,
)

safe_print("\n--- Final Agent Response ---")
messages = result.get("messages", [])
if messages:
    last_msg = messages[-1]
    safe_print(last_msg.content)

safe_print("\n--- Cumulative Application Metrics ---")
stats = llm_usage_tracker.get_stats()
for k, v in stats.items():
    if "cost" in k:
        safe_print(f"  {k}: ${v:.6f}")
    elif "latency" in k:
        safe_print(f"  {k}: {v:.2f}s")
    else:
        safe_print(f"  {k}: {v}")
