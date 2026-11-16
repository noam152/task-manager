"""SQLite persistence, without UI or business validation.

Pass a file-backed database path explicitly to every operation. Initialize it
before CRUD calls. Reads of missing IDs return None; updates and deletes return
False. SQLite errors propagate to the caller. Importing this module creates no
files or connections.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from task_manager.models import Priority, Task

DatabasePath = str | Path


@contextmanager
def get_connection(db_path: DatabasePath) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on error, and always close the connection.

    Parent directories must already exist; initialize_database creates them.
    Separate calls use separate connections, so CRUD requires a file-backed DB.
    """
    connection = sqlite3.connect(db_path, autocommit=False)
    try:
        connection.row_factory = sqlite3.Row
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: DatabasePath) -> None:
    """Create parent directories and the tasks table without deleting data."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # Only fixed enum values form this SQL fragment; user input is always bound.
    priorities = ", ".join(f"'{priority.value}'" for priority in Priority)
    with get_connection(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT '{Priority.MEDIUM.value}'
                    CHECK (priority IN ({priorities})),
                completed INTEGER NOT NULL DEFAULT 0
                    CHECK (completed IN (0, 1))
            )
            """
        )


def _to_task(row: sqlite3.Row) -> Task:
    """Translate SQLite's stored values into the shared Python model."""
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=Priority(row["priority"]),
        completed=bool(row["completed"]),
    )


def create_task(
    db_path: DatabasePath,
    title: str,
    description: str = "",
    priority: Priority = Priority.MEDIUM,
    completed: bool = False,
) -> Task:
    """Insert a task and return it with its generated ID.

    Database constraints enforce non-null fields, priority membership, and a
    boolean completion value. Title trimming/blank checks belong to services.
    """
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """INSERT INTO tasks (title, description, priority, completed)
               VALUES (?, ?, ?, ?)""",
            (title, description, priority, completed),
        )
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _to_task(row)


def get_task(db_path: DatabasePath, task_id: int) -> Task | None:
    """Return the task with this ID, or None when it does not exist."""
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _to_task(row) if row is not None else None


def list_tasks(db_path: DatabasePath) -> list[Task]:
    """Return all tasks in ascending ID order; an empty database returns []."""
    with get_connection(db_path) as connection:
        rows = connection.execute("SELECT * FROM tasks ORDER BY id").fetchall()
        return [_to_task(row) for row in rows]


def update_task(db_path: DatabasePath, task: Task) -> bool:
    """Replace all editable fields by ID; return False if the ID is missing.

    An existing task returns True even when its values are unchanged.
    """
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """UPDATE tasks
               SET title = ?, description = ?, priority = ?, completed = ?
               WHERE id = ?""",
            (task.title, task.description, task.priority, task.completed, task.id),
        )
        return cursor.rowcount > 0


def delete_task(db_path: DatabasePath, task_id: int) -> bool:
    """Delete by ID; return False if absent (including repeated deletes)."""
    with get_connection(db_path) as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0
