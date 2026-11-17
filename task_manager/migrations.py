"""Numbered, transactional schema changes; never rebuild or drop user tables."""

import sqlite3

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


MIGRATIONS = (initial_schema, task_versions)
