"""Persistence tests: every database lives beneath pytest's temporary path."""

import sqlite3
from dataclasses import replace

import pytest

from task_manager.database import (
    create_task,
    delete_task,
    get_connection,
    get_task,
    initialize_database,
    list_tasks,
    update_task,
)
from task_manager.models import Priority, Task


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "tasks.db"
    initialize_database(path)
    return path


def test_initialization_creates_parent_directories_and_schema(tmp_path):
    path = tmp_path / "nested" / "data" / "tasks.db"
    initialize_database(path)

    assert path.is_file()
    with get_connection(path) as connection:
        columns = connection.execute("PRAGMA table_info(tasks)").fetchall()
    assert [column["name"] for column in columns] == [
        "id", "title", "description", "priority", "completed", "version"
    ]
    assert columns[0]["pk"] == 1
    assert list_tasks(path) == []


def test_repeated_initialization_preserves_tasks(db_path):
    task = create_task(db_path, "Keep me")
    initialize_database(db_path)
    initialize_database(db_path)
    assert list_tasks(db_path) == [task]


def test_create_and_get_defaults(db_path):
    task = create_task(db_path, "First task")
    assert isinstance(task, Task)
    assert isinstance(task.id, int) and task.id > 0
    assert task.title == "First task"
    assert task.description == ""
    assert task.priority is Priority.MEDIUM
    assert task.completed is False
    assert get_task(db_path, task.id) == task


@pytest.mark.parametrize("priority", list(Priority))
def test_create_round_trips_all_priorities_and_completed_state(db_path, priority):
    task = create_task(db_path, "Done", "Details", priority, True)
    retrieved = get_task(db_path, task.id)
    assert retrieved == task
    assert retrieved.description == "Details"
    assert retrieved.priority is priority
    assert retrieved.completed is True


def test_list_is_ordered_and_ids_are_not_reused_after_deletion(db_path):
    first = create_task(db_path, "First")
    second = create_task(db_path, "Second")
    assert list_tasks(db_path) == [first, second]
    delete_task(db_path, second.id)
    third = create_task(db_path, "Third")
    assert third.id > second.id
    assert list_tasks(db_path) == [first, third]


def test_update_replaces_all_fields_and_can_reopen_task(db_path):
    task = create_task(db_path, "Original")
    other = create_task(db_path, "Unchanged")
    edited = replace(task, title="Edited", description="Details",
                     priority=Priority.HIGH, completed=True)
    assert update_task(db_path, edited) is True
    assert get_task(db_path, task.id) == replace(edited, version=task.version + 1)
    assert get_task(db_path, other.id) == other
    current = get_task(db_path, task.id)
    assert update_task(db_path, current) is True
    reopened = replace(get_task(db_path, task.id), completed=False)
    assert update_task(db_path, reopened) is True
    assert get_task(db_path, task.id).completed is False


def test_delete_only_removes_selected_task(db_path):
    first = create_task(db_path, "Delete")
    second = create_task(db_path, "Keep")
    assert delete_task(db_path, first.id) is True
    assert get_task(db_path, first.id) is None
    assert list_tasks(db_path) == [second]
    assert delete_task(db_path, first.id) is False


@pytest.mark.parametrize("missing_id", [-1, 0, 999])
def test_missing_ids_do_not_change_data(db_path, missing_id):
    task = create_task(db_path, "Keep")
    assert get_task(db_path, missing_id) is None
    assert update_task(db_path, Task(missing_id, "Missing")) is False
    assert delete_task(db_path, missing_id) is False
    assert list_tasks(db_path) == [task]


def test_changes_persist_across_independent_connections(db_path):
    task = create_task(db_path, "Original")
    edited = replace(task, title="Persisted", completed=True)
    update_task(db_path, edited)
    # An independent raw connection confirms writes were committed to disk.
    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute(
            "SELECT title, completed FROM tasks WHERE id = ?", (task.id,)
        ).fetchone() == ("Persisted", 1)
    finally:
        connection.close()
    assert get_task(db_path, task.id) == replace(edited, version=task.version + 1)
    delete_task(db_path, task.id)
    assert list_tasks(db_path) == []


def test_connection_commits_and_closes_on_success(db_path):
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title) VALUES (?)", ("Saved",)
        )
        task_id = cursor.lastrowid
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    task = get_task(db_path, task_id)
    assert task == Task(task_id, "Saved", "", Priority.MEDIUM, False)
    assert task.priority is Priority.MEDIUM
    assert task.completed is False


def test_connection_rolls_back_and_closes_on_error(db_path):
    with pytest.raises(RuntimeError, match="abort"):
        with get_connection(db_path) as connection:
            connection.execute("INSERT INTO tasks (title) VALUES (?)", ("Lost",))
            raise RuntimeError("abort")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    assert list_tasks(db_path) == []


def test_connection_rolls_back_and_closes_on_commit_failure(db_path):
    existing = create_task(db_path, "Keep")
    with get_connection(db_path) as setup:
        setup.execute("CREATE TABLE parents (id INTEGER PRIMARY KEY)")
        setup.execute(
            """CREATE TABLE children (
                parent_id INTEGER REFERENCES parents(id)
                    DEFERRABLE INITIALLY DEFERRED
            )"""
        )

    body_completed = False
    with pytest.raises(sqlite3.IntegrityError) as error:
        with get_connection(db_path) as connection:
            # SQLite requires enabling foreign keys outside a transaction.
            # Use the public API, then restore transactional mode before writes.
            connection.autocommit = True
            connection.execute("PRAGMA foreign_keys = ON")
            connection.autocommit = False
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

            connection.execute(
                "INSERT INTO tasks (title) VALUES (?)", ("Must roll back",)
            )
            connection.execute(
                "INSERT INTO children (parent_id) VALUES (?)", (999,)
            )
            # Both writes succeed: the violation must surface at context exit.
            assert connection.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 1
            body_completed = True

    assert body_completed
    assert error.value.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    assert list_tasks(db_path) == [existing]
    with get_connection(db_path) as reopened:
        assert reopened.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 0


@pytest.mark.parametrize("field,value", [
    ("title", None),
    ("description", None),
    ("priority", "Urgent"),
    ("priority", "high"),
    ("priority", None),
    ("completed", 2),
    ("completed", None),
])
def test_invalid_insert_is_rejected_without_losing_existing_data(db_path, field, value):
    existing = create_task(db_path, "Keep")
    fields = {"title": "Invalid", field: value}
    with pytest.raises(sqlite3.IntegrityError):
        create_task(db_path, **fields)
    assert list_tasks(db_path) == [existing]


@pytest.mark.parametrize("field,value", [
    ("title", None),
    ("description", None),
    ("priority", "Urgent"),
    ("priority", "high"),
    ("priority", None),
    ("completed", 2),
    ("completed", None),
])
def test_invalid_update_preserves_original_task(db_path, field, value):
    task = create_task(db_path, "Keep", "Original details", Priority.HIGH, True)
    changes = {
        "title": "Changed",
        "description": "Changed details",
        "priority": Priority.LOW,
        "completed": False,
        field: value,
    }
    with pytest.raises(sqlite3.IntegrityError):
        update_task(db_path, replace(task, **changes))
    assert get_task(db_path, task.id) == task
    assert list_tasks(db_path) == [task]


def test_sql_like_text_quotes_and_unicode_round_trip(db_path):
    title = "Robert'); DROP TABLE tasks; --"
    description = "Don't alter this: שלום 📝"
    task = create_task(db_path, title, description)
    assert get_task(db_path, task.id).title == title
    assert get_task(db_path, task.id).description == description
    edited = replace(task, title=description, description=title)
    assert update_task(db_path, edited) is True
    assert list_tasks(db_path) == [replace(edited, version=task.version + 1)]
    assert create_task(db_path, "Table still exists").id > task.id


def test_database_does_not_apply_business_title_validation(db_path):
    task = create_task(db_path, "  ")
    assert get_task(db_path, task.id).title == "  "


def test_paths_are_isolated_and_accept_strings(tmp_path, db_path):
    other_path = str(tmp_path / "other.db")
    initialize_database(other_path)
    first = create_task(db_path, "First database")
    second = create_task(other_path, "Other database")
    assert list_tasks(db_path) == [first]
    assert list_tasks(other_path) == [second]


def test_crud_requires_explicit_initialization(tmp_path):
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        list_tasks(tmp_path / "uninitialized.db")
