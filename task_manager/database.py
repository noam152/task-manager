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
from task_manager import migrations
from task_manager.errors import ConflictError, SchemaError

DatabasePath = str | Path
CONNECTION_TIMEOUT = 5.0


@contextmanager
def get_connection(db_path: DatabasePath) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on error, and always close the connection.

    Parent directories must already exist; initialize_database creates them.
    Separate calls use separate connections, so CRUD requires a file-backed DB.
    """
    connection = sqlite3.connect(db_path, timeout=CONNECTION_TIMEOUT, autocommit=True)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.autocommit = False
        connection.row_factory = sqlite3.Row
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: DatabasePath) -> None:
    """Apply numbered migrations atomically, preserving existing local tasks.

    Migrations take an immediate write lock and recheck the version under that
    lock. Already-current databases take only a short read; failures roll back.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=CONNECTION_TIMEOUT, autocommit=True)
    try:
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        if current > len(migrations.MIGRATIONS):
            raise SchemaError("Database was created by a newer application version.")
        if current == len(migrations.MIGRATIONS):
            return
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        if current > len(migrations.MIGRATIONS):
            raise SchemaError("Database was created by a newer application version.")
        for version, migrate in enumerate(migrations.MIGRATIONS, start=1):
            if version > current:
                migrate(connection)
                connection.execute(f"PRAGMA user_version = {version}")
        connection.execute("COMMIT")
    finally:
        try:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
        finally:
            connection.close()


def _to_task(row: sqlite3.Row) -> Task:
    """Translate SQLite's stored values into the shared Python model."""
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=Priority(row["priority"]),
        completed=bool(row["completed"]),
        version=row["version"],
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

    The supplied version must match. A successful write increments the version,
    including unchanged values. Reload before editing again. Conflicts raise
    ConflictError; missing IDs still return False. The input Task is not mutated.
    """
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """UPDATE tasks
               SET title = ?, description = ?, priority = ?, completed = ?, version = version + 1
               WHERE id = ? AND version = ?""",
            (task.title, task.description, task.priority, task.completed, task.id, task.version),
        )
        if cursor.rowcount:
            return True
        return _missing_or_conflict(connection, task.id)


def _missing_or_conflict(connection: sqlite3.Connection, task_id: int) -> bool:
    if connection.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
        raise ConflictError("This task changed in another session. Reload before trying again.")
    return False


def set_task_completed(db_path: DatabasePath, task_id: int, completed: bool) -> bool:
    """Atomically update only completion; never overwrite task details.

    Repeating the current state succeeds without changing its version.
    """
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """UPDATE tasks SET completed = ?, version = version + (completed != ?)
               WHERE id = ?""", (completed, completed, task_id)
        )
        return cursor.rowcount > 0


def delete_task(db_path: DatabasePath, task_id: int, *, expected_version: int | None = None) -> bool:
    """Delete by ID, optionally checking the revision shown for confirmation."""
    with get_connection(db_path) as connection:
        if expected_version is None:
            cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        else:
            cursor = connection.execute(
                "DELETE FROM tasks WHERE id = ? AND version = ?", (task_id, expected_version)
            )
        if cursor.rowcount:
            return True
        return _missing_or_conflict(connection, task_id)
