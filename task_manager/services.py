"""Task validation and business operations, independent of SQL and UI.

Call database.initialize_database explicitly before use. Invalid field values or
filters raise ValueError before database access. Database errors propagate.
Missing IDs follow persistence semantics: None for reads, False for mutations.
"""

from dataclasses import replace
from typing import Literal
from datetime import date

from task_manager import database
from task_manager.database import DatabasePath
from task_manager.models import Priority, Task, TaskPage, TaskSummary

StatusFilter = Literal["All", "Pending", "Completed"]
SORT_ORDERS = ("id", "created_desc", "created_asc", "priority", "due_date")


def _validate_organization(due_date: date | None, category: str) -> tuple[date | None, str]:
    if due_date is not None and type(due_date) is not date:
        raise ValueError("Due date must be a calendar date or None.")
    if not isinstance(category, str) or len(category.strip()) > 80:
        raise ValueError("Category must be a string of at most 80 characters.")
    return due_date, category.strip()


def _validate_id(task_id: int) -> None:
    if type(task_id) is not int:
        raise ValueError("Task ID must be an integer.")


def _validate_version(version: int) -> None:
    if type(version) is not int or version < 1:
        raise ValueError("Version must be a positive integer.")


def _validate_fields(
    title: str, description: str, priority: Priority | str, completed: bool
) -> tuple[str, str, Priority, bool]:
    """Normalize the title and priority; preserve description text verbatim."""
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise ValueError("Title must be a non-empty string of at most 200 characters.")
    if not isinstance(description, str) or len(description) > 10000:
        raise ValueError("Description must be a string of at most 10000 characters.")
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
    *,
    due_date: date | None = None,
    category: str = "",
) -> Task:
    """Create a task after validating fields and stripping title whitespace."""
    fields = _validate_fields(title, description, priority, completed)
    due_date, category = _validate_organization(due_date, category)
    return database.create_task(db_path, *fields, due_date=due_date, category=category)


def get_task(db_path: DatabasePath, task_id: int) -> Task | None:
    """Return a task, or None if the ID does not exist."""
    _validate_id(task_id)
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
    _validate_id(task.id)
    _validate_version(task.version)
    due_date, category = _validate_organization(task.due_date, task.category)
    validated = replace(
        task, title=title, description=description,
        priority=priority, completed=completed,
        due_date=due_date, category=category,
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
    _validate_id(task_id)
    return database.set_task_completed(db_path, task_id, completed)


def delete_task(db_path: DatabasePath, task_id: int, *, expected_version: int | None = None) -> bool:
    """Delete a task; return False if absent or already deleted."""
    _validate_id(task_id)
    if expected_version is not None:
        _validate_version(expected_version)
    return database.delete_task(db_path, task_id, expected_version=expected_version)


def _query_filters(
    status: StatusFilter, search: str, category: str | None, sort: str
) -> dict:
    if status not in ("All", "Pending", "Completed"):
        raise ValueError("Status must be All, Pending, or Completed.")
    if not isinstance(search, str) or len(search) > 200:
        raise ValueError("Search must be a string of at most 200 characters.")
    if category is not None:
        _, category = _validate_organization(None, category)
    if sort not in SORT_ORDERS:
        raise ValueError("Unsupported sort order.")
    return dict(completed=None if status == "All" else status == "Completed",
                search=search.strip(), category=category, sort=sort)


def list_tasks(
    db_path: DatabasePath, status: StatusFilter = "All", *, search: str = "",
    category: str | None = None, sort: str = "id",
) -> list[Task]:
    """Filter in SQLite; intended for exports/tests, use pages for the UI."""
    return database.list_tasks(db_path, **_query_filters(status, search, category, sort))


def get_task_page(
    db_path: DatabasePath, status: StatusFilter = "All", *, search: str = "",
    category: str | None = None, sort: str = "id", page: int = 1, page_size: int = 10,
) -> TaskPage:
    filters = _query_filters(status, search, category, sort)
    if type(page) is not int or page < 1:
        raise ValueError("Page must be a positive integer.")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("Page size must be between 1 and 100.")
    return database.get_task_page(db_path, **filters, page=page, page_size=page_size)


def get_summary(db_path: DatabasePath, *, today: date | None = None) -> TaskSummary:
    today = date.today() if today is None else today
    if type(today) is not date:
        raise ValueError("Today must be a calendar date.")
    return database.get_summary(db_path, today)


def list_categories(db_path: DatabasePath) -> list[str]:
    return database.list_categories(db_path)
