import sqlglot
from sqlglot import exp


def classify_sql(query: str) -> str:
    """
    Classify SQL into:
    - read
    - write
    - blocked
    """

    try:
        statements = sqlglot.parse(
            query,
            read="postgres"
        )

    except Exception:
        return "blocked"

    if len(statements) != 1:
        return "blocked"

    statement = statements[0]

    if isinstance(statement, exp.Select):
        return "read"

    if isinstance(
        statement,
        (
            exp.Insert,
            exp.Update,
            exp.Delete,
        )
    ):
        return "write"

    return "blocked"