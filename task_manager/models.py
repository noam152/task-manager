"""Task data shared by persistence and future application layers."""

from dataclasses import dataclass
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
