from typing import Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolArg
from langgraph.prebuilt import InjectedState

from app.db.connection import db, Database
from app.security.sql_guard import validate_sql
from app.state import AgentState


MAX_ROWS = 20


@tool
def execute_sql(
    query: str,
    config: Annotated[Optional[RunnableConfig], InjectedToolArg] = None,
    state: Annotated[AgentState, InjectedState] = None,
) -> str:
    """Execute a SQL query against the database (SELECT, INSERT, UPDATE, DELETE)."""

    # Check if write operation was approved by human
    is_approved = False
    if state and isinstance(state, dict):
        is_approved = state.get("approval_status") == "approved"
    elif config and "configurable" in config:
        is_approved = config["configurable"].get("approval_status") == "approved"

    # =========================================
    # 1. Validate SQL
    # =========================================

    is_valid, message = validate_sql(query, allow_write=is_approved)

    if not is_valid:
        return f"SQL_BLOCKED: {message}"


    connection = None
    cursor = None

    try:

        # =====================================
        # 2. Get database object from runtime config or default
        # =====================================

        db_instance: Database = db
        if config and "configurable" in config:
            db_instance = config["configurable"].get("db", db)

        connection = db_instance.get_connection()

        cursor = connection.cursor()

        # =====================================
        # 3. Execute query
        # =====================================

        cursor.execute(query)

        # =====================================
        # 4. Handle query results
        # =====================================

        if cursor.description is not None:
            rows = cursor.fetchmany(MAX_ROWS + 1)
            columns = [description[0] for description in cursor.description]
            has_more = len(rows) > MAX_ROWS
            display_rows = rows[:MAX_ROWS]

            result = [dict(zip(columns, row)) for row in display_rows]
            output = f"SQL_SUCCESS ({len(display_rows)} rows):\n{result}"
            if has_more:
                output += f"\n... (truncated, showing first {MAX_ROWS} rows)"
            return output
        else:
            connection.commit()
            return f"SQL_SUCCESS: {cursor.rowcount} row(s) affected."

    except Exception as exc:

        if connection:
            connection.rollback()

        return f"SQL_EXECUTION_ERROR: {str(exc)}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()