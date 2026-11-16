from langchain_core.tools import tool

from app.db.connection import get_connection


@tool
def execute_write_sql(query: str) -> str:
    """
    Execute an approved database write operation.

    IMPORTANT:
    This tool should only be reachable after the
    human approval node.
    """

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute(query)

        affected_rows = cursor.rowcount

        connection.commit()

        return (
            "WRITE_SUCCESS: "
            f"{affected_rows} row(s) affected."
        )

    except Exception as exc:

        if connection:
            connection.rollback()

        return (
            "WRITE_ERROR: "
            f"{str(exc)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()