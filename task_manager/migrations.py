"""Numbered, transactional schema changes; never rebuild or drop user tables."""

import sqlite3
from datetime import UTC, datetime

from task_manager.errors import SchemaError


def initial_schema(connection: sqlite3.Connection) -> None:
    """Adopt the original unversioned schema or create it for a new database."""
    connection.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'Medium'
                CHECK (priority IN ('Low', 'Medium', 'High')),
            completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1))
        )"""
    )
    columns = [row[1] for row in connection.execute("PRAGMA table_info(tasks)")]
    if columns != ["id", "title", "description", "priority", "completed"]:
        raise SchemaError("Unrecognized unversioned tasks schema; restore a known backup.")


def task_versions(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE tasks ADD COLUMN version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)"
    )


def task_organization(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
    connection.execute("ALTER TABLE tasks ADD COLUMN category TEXT NOT NULL DEFAULT ''")
    connection.execute("ALTER TABLE tasks ADD COLUMN created_at TEXT")
    # The original app did not record creation times; record upgrade time for it.
    timestamp = datetime.now(UTC).isoformat(timespec="microseconds")
    connection.execute("UPDATE tasks SET created_at = ?", (timestamp,))
    connection.execute("CREATE INDEX tasks_status_id ON tasks(completed, id)")
    connection.execute("CREATE INDEX tasks_category_status ON tasks(category, completed, id)")
    connection.execute("CREATE INDEX tasks_due ON tasks(due_date, id) WHERE completed = 0")
    connection.execute("CREATE INDEX tasks_created ON tasks(created_at DESC, id DESC)")
    connection.execute(
        """CREATE INDEX tasks_priority ON tasks(
            CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, id)"""
    )


MIGRATIONS = (initial_schema, task_versions, task_organization)
