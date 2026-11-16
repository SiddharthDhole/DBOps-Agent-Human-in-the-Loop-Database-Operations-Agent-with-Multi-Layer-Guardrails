from typing import Annotated, Optional
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolArg

from app.db.connection import db, Database


@tool
def get_database_schema(
    config: Annotated[Optional[RunnableConfig], InjectedToolArg] = None
) -> str:
    """Retrieve database schema, tables, columns, and foreign keys."""

    db_instance: Database = db
    if config and "configurable" in config:
        db_instance = config["configurable"].get("db", db)

    connection = db_instance.get_connection()

    try:
        cursor = connection.cursor()

        # Get business tables & columns (ignore internal checkpoints)
        cursor.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name NOT LIKE 'checkpoint%'
            ORDER BY table_name, ordinal_position;
            """
        )
        columns = cursor.fetchall()

        # Get primary keys
        cursor.execute(
            """
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name NOT LIKE 'checkpoint%';
            """
        )
        primary_keys = {}
        for tbl, col in cursor.fetchall():
            primary_keys.setdefault(tbl, []).append(col)

        # Get foreign keys
        cursor.execute(
            """
            SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name NOT LIKE 'checkpoint%';
            """
        )
        foreign_keys = {}
        for tbl, col, ftbl, fcol in cursor.fetchall():
            foreign_keys.setdefault(tbl, []).append(f"{col}->{ftbl}.{fcol}")

        # Group columns by table
        tables = {}
        for tbl, col, dtype in columns:
            tables.setdefault(tbl, []).append(f"{col} {dtype}")

        lines = []
        for tbl, cols in tables.items():
            col_str = ", ".join(cols)
            pks = f" | PK: {', '.join(primary_keys[tbl])}" if tbl in primary_keys else ""
            fks = f" | FK: {', '.join(foreign_keys[tbl])}" if tbl in foreign_keys else ""
            lines.append(f"• {tbl} ({col_str}){pks}{fks}")

        return "\n".join(lines) if lines else "No tables found."

    finally:
        cursor.close()
        connection.close()