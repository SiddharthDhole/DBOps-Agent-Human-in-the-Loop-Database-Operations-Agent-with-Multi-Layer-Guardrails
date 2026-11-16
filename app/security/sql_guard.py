import sqlglot
from sqlglot import exp


MAX_QUERY_LENGTH = 5000


def validate_sql(query: str, allow_write: bool = False) -> tuple[bool, str]:
    """
    Validate SQL before it reaches PostgreSQL.

    Policy:
    - Only one statement
    - SELECT queries are always allowed
    - DML write operations (INSERT, UPDATE, DELETE) require allow_write=True
    - Destructive DDL / DCL / admin statements (DROP, ALTER, TRUNCATE, CREATE, etc.) are strictly prohibited
    - PostgreSQL dialect
    """

    if not query or not query.strip():
        return False, "SQL query cannot be empty."

    query = query.strip()

    # Basic resource protection
    if len(query) > MAX_QUERY_LENGTH:
        return False, "SQL query is too long."

    try:
        statements = sqlglot.parse(
            query,
            read="postgres"
        )
    except Exception as exc:
        return False, f"Invalid SQL syntax: {exc}"

    # Only one statement
    if len(statements) != 1:
        return False, "Only one SQL statement is allowed."

    statement = statements[0]

    # SELECT queries are always allowed
    if isinstance(statement, exp.Select):
        return True, "SQL query allowed."

    # DML write operations require explicit human approval (allow_write=True)
    if isinstance(
        statement,
        (
            exp.Insert,
            exp.Update,
            exp.Delete,
        )
    ):
        if allow_write:
            return True, "SQL query allowed."
        return False, "Write operations (INSERT, UPDATE, DELETE) require explicit human approval."

    # Destructive DDL / administrative operations are prohibited
    return False, "Destructive operations and DDL statements (DROP, ALTER, TRUNCATE, etc.) are strictly prohibited."