"""Task validation and business operations, independent of SQL and UI.

Call database.initialize_database explicitly before use. Invalid field values or
filters raise ValueError before database access. Database errors propagate.
Missing IDs follow persistence semantics: None for reads, False for mutations.
"""

from dataclasses import replace
from typing import Literal

from task_manager import database
from task_manager.database import DatabasePath
from task_manager.models import Priority, Task

StatusFilter = Literal["All", "Pending", "Completed"]


def _validate_fields(
    title: str, description: str, priority: Priority | str, completed: bool
) -> tuple[str, str, Priority, bool]:
    """Normalize the title and priority; preserve description text verbatim."""
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Title must be a non-empty string.")
    if not isinstance(description, str):
        raise ValueError("Description must be a string.")
    try:
        normalized_priority = Priority(priority)
    except (ValueError, TypeError):
        raise ValueError("Priority must be Low, Medium, or High.") from None
    if not isinstance(completed, bool):
        raise ValueError("Completed must be a boolean.")
    return title.strip(), description, normalized_priority, completed


def create_task(
    db_path: DatabasePath,
    title: str,
    description: str = "",
    priority: Priority | str = Priority.MEDIUM,
    completed: bool = False,
) -> Task:
    """Create a task after validating fields and stripping title whitespace."""
    fields = _validate_fields(title, description, priority, completed)
    return database.create_task(db_path, *fields)


def get_task(db_path: DatabasePath, task_id: int) -> Task | None:
    """Return a task, or None if the ID does not exist."""
    return database.get_task(db_path, task_id)


def update_task(db_path: DatabasePath, task: Task) -> bool:
    """Replace all editable fields; validate even if the ID does not exist.

    Returns False for a missing ID, True for an existing task (even unchanged).
    The supplied Task is never mutated. Use dataclasses.replace for edits that
    preserve other fields, including completion state.
    """
    title, description, priority, completed = _validate_fields(
        task.title, task.description, task.priority, task.completed
    )
    validated = replace(
        task, title=title, description=description,
        priority=priority, completed=completed,
    )
    return database.update_task(db_path, validated)


def set_task_completed(
    db_path: DatabasePath, task_id: int, completed: bool
) -> bool:
    """Complete (True) or reopen (False) a task without changing its text.

    Repeating the current state succeeds. Missing IDs return False; an invalid
    completion value raises ValueError before looking up the task.
    """
    if not isinstance(completed, bool):
        raise ValueError("Completed must be a boolean.")
    return database.set_task_completed(db_path, task_id, completed)


def delete_task(db_path: DatabasePath, task_id: int, *, expected_version: int | None = None) -> bool:
    """Delete a task; return False if absent or already deleted."""
    return database.delete_task(db_path, task_id, expected_version=expected_version)


def list_tasks(
    db_path: DatabasePath, status: StatusFilter = "All"
) -> list[Task]:
    """Filter by exact status label while preserving ascending ID order."""
    if status not in ("All", "Pending", "Completed"):
        raise ValueError("Status must be All, Pending, or Completed.")
    tasks = database.list_tasks(db_path)
    if status == "All":
        return tasks
    completed = status == "Completed"
    return [task for task in tasks if task.completed == completed]
