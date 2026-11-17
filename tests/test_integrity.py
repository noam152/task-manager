"""Deterministic migration, stale-write and simultaneous-writer regressions."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from task_manager import database, migrations, services
from task_manager.errors import ConflictError, SchemaError


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "integrity.db"
    database.initialize_database(path)
    return path


def test_migrate_original_database_without_changing_user_data(tmp_path):
    path = tmp_path / "original.db"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'Medium'
                    CHECK (priority IN ('Low', 'Medium', 'High')),
                completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)))"""
        )
        connection.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)", (42, "Keep", "Details", "High", 1)
        )
        connection.commit()
    finally:
        connection.close()
    database.initialize_database(path)
    database.initialize_database(path)
    task = database.get_task(path, 42)
    assert (task.id, task.title, task.description, task.priority, task.completed, task.version) == (
        42, "Keep", "Details", "High", True, 1
    )
    assert database.create_task(path, "Next").id > 42
    with database.get_connection(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == len(migrations.MIGRATIONS)


def test_failed_migration_rolls_back_ddl_and_version(db_path, monkeypatch):
    task = database.create_task(db_path, "Keep")
    original = migrations.MIGRATIONS

    def broken(connection):
        connection.execute("ALTER TABLE tasks ADD COLUMN must_not_persist TEXT")
        raise RuntimeError("migration failed")

    monkeypatch.setattr(migrations, "MIGRATIONS", (*original, broken))
    with pytest.raises(RuntimeError, match="migration failed"):
        database.initialize_database(db_path)
    with database.get_connection(db_path) as connection:
        assert "must_not_persist" not in [row[1] for row in connection.execute("PRAGMA table_info(tasks)")]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == len(original)
    assert database.get_task(db_path, task.id) == task
    monkeypatch.setattr(migrations, "MIGRATIONS", original)
    database.initialize_database(db_path)


def test_newer_schema_is_rejected_without_touching_data(db_path):
    task = database.create_task(db_path, "Keep")
    with database.get_connection(db_path) as connection:
        connection.execute("PRAGMA user_version = 999")
    with pytest.raises(SchemaError, match="newer"):
        database.initialize_database(db_path)
    assert database.get_task(db_path, task.id) == task


def test_unknown_legacy_schema_is_not_adopted(tmp_path):
    path = tmp_path / "unknown.db"
    with database.get_connection(path) as connection:
        connection.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, unrelated TEXT)")
        connection.execute("INSERT INTO tasks VALUES (1, 'Keep')")
    with pytest.raises(SchemaError, match="Unrecognized"):
        database.initialize_database(path)
    with database.get_connection(path) as connection:
        assert tuple(connection.execute("SELECT * FROM tasks").fetchone()) == (1, "Keep")
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_stale_edits_cannot_overwrite_newer_details(db_path):
    original = services.create_task(db_path, "Original")
    services.update_task(db_path, replace(original, description="New details"))
    with pytest.raises(ConflictError):
        services.update_task(db_path, replace(original, title="Stale"))
    current = services.get_task(db_path, original.id)
    assert current.title == "Original"
    assert current.description == "New details"
    assert current.version == 2


def test_completion_preserves_concurrent_details_and_invalidates_old_edits(db_path, monkeypatch):
    task = services.create_task(db_path, "Original")
    services.update_task(db_path, replace(task, title="New title"))
    # Completion must not do a read/modify/full-row write in the service layer.
    with monkeypatch.context() as patch:
        patch.setattr(database, "get_task", lambda *args: pytest.fail("Unexpected read"))
        assert services.set_task_completed(db_path, task.id, True)
    current = services.get_task(db_path, task.id)
    assert current.title == "New title" and current.completed is True
    assert current.version == 3
    assert services.set_task_completed(db_path, task.id, True)
    assert services.get_task(db_path, task.id).version == 3
    with pytest.raises(ConflictError):
        services.update_task(db_path, replace(task, title="Stale"))


def test_simultaneous_writers_have_one_winner_and_one_conflict(db_path):
    task = services.create_task(db_path, "Original")
    barrier = Barrier(2)

    def edit(title):
        snapshot = services.get_task(db_path, task.id)
        barrier.wait(timeout=5)
        try:
            services.update_task(db_path, replace(snapshot, title=title))
            return "saved", title
        except ConflictError:
            return "conflict", title

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, ["First", "Second"]))
    assert sorted(result[0] for result in results) == ["conflict", "saved"]
    winner = next(title for result, title in results if result == "saved")
    current = services.get_task(db_path, task.id)
    assert current.title == winner and current.version == 2


def test_simultaneous_initialization_is_safe(tmp_path):
    path = tmp_path / "simultaneous.db"
    barrier = Barrier(2)

    def initialize(_):
        barrier.wait(timeout=5)
        database.initialize_database(path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(initialize, range(2)))
    assert database.list_tasks(path) == []


def test_locked_write_fails_without_partial_changes_and_can_be_retried(db_path, monkeypatch):
    task = services.create_task(db_path, "Keep")
    monkeypatch.setattr(database, "CONNECTION_TIMEOUT", 0)
    with database.get_connection(db_path) as holder:
        holder.execute("UPDATE tasks SET title = 'Holding lock' WHERE id = ?", (task.id,))
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            services.set_task_completed(db_path, task.id, True)
        holder.rollback()
    assert services.get_task(db_path, task.id) == task
    assert services.set_task_completed(db_path, task.id, True)


def test_version_checked_delete_refuses_changed_task(db_path):
    task = services.create_task(db_path, "Keep")
    services.set_task_completed(db_path, task.id, True)
    with pytest.raises(ConflictError):
        services.delete_task(db_path, task.id, expected_version=task.version)
    current = services.get_task(db_path, task.id)
    assert services.delete_task(db_path, task.id, expected_version=current.version)
    assert not services.delete_task(db_path, task.id, expected_version=current.version)
