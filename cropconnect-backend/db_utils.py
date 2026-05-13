import logging
import re

logger = logging.getLogger("cropconnect")


def quote_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name or ""):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return f"`{name}`"


def table_exists(cursor, table_schema: str, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (table_schema, table_name),
    )
    row = cursor.fetchone()
    count = row["count"] if isinstance(row, dict) else row[0]
    return bool(count)


def column_exists(cursor, table_schema: str, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table_schema, table_name, column_name),
    )
    row = cursor.fetchone()
    count = row["count"] if isinstance(row, dict) else row[0]
    return bool(count)


def add_column_if_missing(cursor, table_schema: str, table_name: str, column_name: str, definition: str) -> None:
    if not column_exists(cursor, table_schema, table_name, column_name):
        cursor.execute(f"ALTER TABLE {quote_identifier(table_name)} ADD COLUMN {quote_identifier(column_name)} {definition}")


def drop_column_if_exists(cursor, table_schema: str, table_name: str, column_name: str) -> None:
    if column_exists(cursor, table_schema, table_name, column_name):
        cursor.execute(f"ALTER TABLE {quote_identifier(table_name)} DROP COLUMN {quote_identifier(column_name)}")


def modify_column_best_effort(cursor, table_name: str, column_name: str, definition: str) -> None:
    try:
        cursor.execute(f"ALTER TABLE {quote_identifier(table_name)} MODIFY COLUMN {quote_identifier(column_name)} {definition}")
    except Exception as exc:
        logger.warning("Column modify skipped for %s.%s: %s", table_name, column_name, exc)


def index_exists(cursor, table_schema: str, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (table_schema, table_name, index_name),
    )
    row = cursor.fetchone()
    count = row["count"] if isinstance(row, dict) else row[0]
    return bool(count)
