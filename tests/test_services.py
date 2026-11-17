"""Unit validation checks and integration tests using temporary databases."""

import sqlite3
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from task_manager import database, services
from task_manager.models import Priority, Task


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "services.db"
    database.initialize_database(path)
    return path


INVALID_FIELDS = [
    ("title", ""),
    ("title", " \t\n "),
    ("title", None),
    ("title", 123),
    ("description", None),
    ("description", 123),
    ("priority", "Urgent"),
    ("priority", "high"),
    ("priority", " High "),
    ("priority", None),
    ("completed", 1),
    ("completed", None),
]


@pytest.mark.parametrize("field,value", INVALID_FIELDS)
def test_invalid_creation_never_calls_persistence(monkeypatch, field, value):
    create = Mock()
    monkeypatch.setattr(database, "create_task", create)
    fields = {"title": "Valid", field: value}
    with pytest.raises(ValueError):
        services.create_task("unused.db", **fields)
    create.assert_not_called()


@pytest.mark.parametrize("field,value", INVALID_FIELDS)
def test_invalid_update_preserves_persisted_task(db_path, field, value):
    task = services.create_task(db_path, "Keep", "Original", Priority.HIGH, True)
    changes = {"title": "Changed", "description": "Changed", field: value}
    with pytest.raises(ValueError):
        services.update_task(db_path, replace(task, **changes))
    assert database.get_task(db_path, task.id) == task


@pytest.mark.parametrize("priority", [*Priority, "Low", "Medium", "High"])
def test_creation_accepts_enums_and_exact_labels(db_path, priority):
    task = services.create_task(db_path, "  Task \n", "  Details\n", priority)
    assert task.title == "Task"
    assert task.description == "  Details\n"
    assert task.priority is Priority(priority)
    assert task.completed is False
    assert services.get_task(db_path, task.id) == task


def test_creation_defaults_and_duplicate_titles(db_path):
    first = services.create_task(db_path, "Same")
    second = services.create_task(db_path, "Same")
    assert first.description == ""
    assert first.priority is Priority.MEDIUM
    assert first.completed is False
    assert first.id != second.id
    assert services.list_tasks(db_path) == [first, second]


def test_update_changes_fields_without_mutating_input(db_path):
    original = services.create_task(db_path, "Original", completed=True)
    edited = replace(original, title="  Edited ", description="", priority="Low")
    assert services.update_task(db_path, edited) is True
    expected = replace(original, title="Edited", description="", priority=Priority.LOW, version=2)
    assert services.get_task(db_path, original.id) == expected
    assert edited.title == "  Edited "
    assert original.title == "Original"
    assert services.update_task(db_path, expected) is True


def test_complete_reopen_and_repeat_preserve_other_fields(db_path):
    task = services.create_task(db_path, "Keep", "Details", Priority.HIGH)
    for state, version in ((True, 2), (True, 2), (False, 3), (False, 3)):
        assert services.set_task_completed(db_path, task.id, state) is True
        result = services.get_task(db_path, task.id)
        assert result == replace(task, completed=state, version=version)
        assert result.completed is state


@pytest.mark.parametrize("value", [None, 0, 1, "False"])
def test_invalid_completion_never_looks_up_task(monkeypatch, value):
    lookup = Mock()
    monkeypatch.setattr(database, "get_task", lookup)
    with pytest.raises(ValueError, match="boolean"):
        services.set_task_completed("unused.db", 999, value)
    lookup.assert_not_called()


@pytest.mark.parametrize("missing_id", [-1, 0, 999])
def test_missing_ids_follow_database_semantics(db_path, missing_id):
    existing = services.create_task(db_path, "Keep")
    assert services.get_task(db_path, missing_id) is None
    assert services.update_task(db_path, Task(missing_id, "Missing")) is False
    assert services.set_task_completed(db_path, missing_id, True) is False
    assert services.set_task_completed(db_path, missing_id, False) is False
    assert services.delete_task(db_path, missing_id) is False
    assert services.list_tasks(db_path) == [existing]


def test_update_validates_before_database_access_even_for_missing_id(monkeypatch):
    update = Mock()
    monkeypatch.setattr(database, "update_task", update)
    with pytest.raises(ValueError):
        services.update_task("unused.db", Task(999, "  "))
    update.assert_not_called()


def test_delete_and_repeat_preserve_other_tasks(db_path):
    first = services.create_task(db_path, "Delete")
    second = services.create_task(db_path, "Keep")
    assert services.delete_task(db_path, first.id) is True
    assert services.get_task(db_path, first.id) is None
    assert services.delete_task(db_path, first.id) is False
    assert services.list_tasks(db_path) == [second]


@pytest.mark.parametrize("status", ["All", "Pending", "Completed"])
def test_filters_preserve_order_and_follow_completion_changes(db_path, status):
    first = services.create_task(db_path, "First")
    second = services.create_task(db_path, "Second", completed=True)
    third = services.create_task(db_path, "Third")
    expected = {
        "All": [first, second, third],
        "Pending": [first, third],
        "Completed": [second],
    }
    assert services.list_tasks(db_path, status) == expected[status]
    services.set_task_completed(db_path, first.id, True)
    services.set_task_completed(db_path, second.id, False)
    expected = {
        "All": [
            replace(first, completed=True, version=2),
            replace(second, completed=False, version=2),
            third,
        ],
        "Pending": [replace(second, completed=False, version=2), third],
        "Completed": [replace(first, completed=True, version=2)],
    }
    assert services.list_tasks(db_path, status) == expected[status]


@pytest.mark.parametrize("status", ["All", "Pending", "Completed"])
def test_empty_database_filters(db_path, status):
    assert services.list_tasks(db_path, status) == []


@pytest.mark.parametrize("status", ["", "all", "Unknown", None])
def test_invalid_filter_never_reads_database(monkeypatch, status):
    listing = Mock()
    monkeypatch.setattr(database, "list_tasks", listing)
    with pytest.raises(ValueError, match="Status"):
        services.list_tasks("unused.db", status)
    listing.assert_not_called()


def test_explicit_paths_keep_databases_isolated(db_path, tmp_path):
    other = str(tmp_path / "other.db")
    database.initialize_database(other)
    task = services.create_task(db_path, "Only here")
    assert services.list_tasks(db_path) == [task]
    assert services.list_tasks(other) == []


def test_text_is_preserved_without_sql_interpretation(db_path):
    text = "Don't drop tasks; -- שלום"
    task = services.create_task(db_path, text, text)
    assert services.get_task(db_path, task.id) == task
    assert task.title == task.description == text
    assert services.create_task(db_path, "Still works").id > task.id


def test_database_errors_propagate(monkeypatch):
    error = sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(database, "create_task", Mock(side_effect=error))
    with pytest.raises(sqlite3.OperationalError) as caught:
        services.create_task("unused.db", "Valid")
    assert caught.value is error
