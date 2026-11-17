"""Task data shared by persistence and future application layers."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class Priority(StrEnum):
    """The supported priorities, in display order."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class Task:
    """A persisted task; IDs are assigned by SQLite during creation."""

    id: int
    title: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    completed: bool = False
    version: int = 1
    due_date: date | None = None
    category: str = ""
    created_at: datetime | None = None

    def is_overdue(self, today: date) -> bool:
        """Due dates are calendar dates; completed tasks are never overdue."""
        return not self.completed and self.due_date is not None and self.due_date < today


@dataclass(frozen=True)
class TaskSummary:
    total: int
    pending: int
    completed: int
    overdue: int


@dataclass(frozen=True)
class TaskPage:
    tasks: list[Task]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)
