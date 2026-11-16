import os
from typing import Optional

import psycopg2
from dotenv import load_dotenv


load_dotenv()


class Database:
    """PostgreSQL Database manager for DBOps."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.host = host or os.getenv("DB_HOST", "localhost")
        self.port = port or os.getenv("DB_PORT", "5432")
        self.user = user or os.getenv("DB_USER", "postgres")
        self.password = password or os.getenv("DB_PASSWORD", "pass@1234")
        self.database = database or os.getenv("DB_NAME", "dbops_demo")

    def get_connection(self):
        """Create and return a new PostgreSQL connection."""
        return psycopg2.connect(
            user=self.user,
            password=self.password,
            database=self.database,
            host=self.host,
            port=self.port,
        )


# Default database instance
db = Database()


def get_connection():
    """Convenience function returning a connection from default db."""
    return db.get_connection()