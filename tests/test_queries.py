"""V2 fields, SQL queries, summary counts and validation boundaries."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock

import pytest

from task_manager import database, services
from task_manager.models import Priority, TaskSummary


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "queries.db"
    database.initialize_database(path)
    return path


def test_organization_fields_round_trip_and_can_be_cleared(db_path):
    task = services.create_task(db_path, "Plan", due_date=date(2030, 1, 2), category="  Work  ")
    assert task.due_date == date(2030, 1, 2)
    assert task.category == "Work"
    assert task.created_at.tzinfo is not None
    assert task.created_at.utcoffset() == timedelta(0)
    assert services.get_task(db_path, task.id) == task
    services.update_task(db_path, replace(task, due_date=None, category=""))
    current = services.get_task(db_path, task.id)
    assert current == replace(task, due_date=None, category="", version=2)
    assert current.created_at == task.created_at


@pytest.mark.parametrize("due_date", ["2030-01-01", datetime(2030, 1, 1), 1, False])
def test_invalid_due_dates_fail_before_persistence(monkeypatch, due_date):
    create = Mock()
    monkeypatch.setattr(database, "create_task", create)
    with pytest.raises(ValueError, match="calendar date"):
        services.create_task("unused.db", "Task", due_date=due_date)
    create.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "x" * 201),
        ("description", "x" * 10001),
        ("category", "x" * 81),
        ("category", None),
        ("category", 1),
    ],
)
def test_invalid_fields_leave_data_unchanged(db_path, field, value):
    task = services.create_task(db_path, "Keep")
    with pytest.raises(ValueError):
        services.create_task(db_path, **{"title": "Invalid", field: value})
    with pytest.raises(ValueError):
        services.update_task(db_path, replace(task, **{field: value}))
    assert services.list_tasks(db_path) == [task]


def test_valid_length_boundaries(db_path):
    task = services.create_task(db_path, "x" * 200, "d" * 10000, category="c" * 80)
    assert services.get_task(db_path, task.id) == task


@pytest.mark.parametrize("status", ["All", "Pending", "Completed"])
@pytest.mark.parametrize("category", [None, "Work", ""])
def test_combined_filters_are_consistent_with_pagination(db_path, status, category):
    tasks = [
        services.create_task(db_path, "Needle one", category="Work"),
        services.create_task(db_path, "Other", "Contains NEEDLE", category="Work", completed=True),
        services.create_task(db_path, "Needle two"),
        services.create_task(db_path, "Unrelated", category="Work"),
    ]
    expected = [
        t
        for t in tasks[:3]
        if (status == "All" or t.completed == (status == "Completed"))
        and (category is None or t.category == category)
    ]
    result = services.list_tasks(db_path, status, search="needle", category=category)
    page = services.get_task_page(db_path, status, search="needle", category=category)
    assert result == expected == page.tasks
    assert page.total == len(expected)


@pytest.mark.parametrize("text", ["100%", "a_b", "a\\b", "'); DROP TABLE tasks; --", "שלום"])
def test_search_is_literal_and_parameterized(db_path, text):
    task = services.create_task(db_path, text)
    services.create_task(db_path, "Unrelated")
    assert services.list_tasks(db_path, search=text) == [task]
    assert len(services.list_tasks(db_path)) == 2


def test_priority_due_date_and_creation_sorting(db_path):
    low = services.create_task(db_path, "Low", priority=Priority.LOW)
    high = services.create_task(db_path, "High", priority=Priority.HIGH, due_date=date(2030, 1, 2))
    medium = services.create_task(db_path, "Medium", due_date=date(2030, 1, 1))
    tie = services.create_task(db_path, "Tie", due_date=date(2030, 1, 1))
    assert services.list_tasks(db_path, sort="priority") == [high, medium, tie, low]
    assert services.list_tasks(db_path, sort="due_date") == [medium, tie, high, low]
    assert services.list_tasks(db_path, sort="created_desc") == [tie, medium, high, low]
    assert services.list_tasks(db_path, sort="created_asc") == [low, high, medium, tie]


def test_pages_are_bounded_and_clamped_after_deletions(db_path):
    tasks = [services.create_task(db_path, f"Task {i}") for i in range(23)]
    first = services.get_task_page(db_path, page_size=10)
    last = services.get_task_page(db_path, page=999, page_size=10)
    assert first.tasks == tasks[:10] and first.total == 23 and first.pages == 3
    assert last.tasks == tasks[20:] and last.page == 3
    for task in last.tasks:
        services.delete_task(db_path, task.id)
    clamped = services.get_task_page(db_path, page=3, page_size=10)
    assert clamped.page == 2 and clamped.tasks == tasks[10:20]
    empty = services.get_task_page(db_path, search="Nothing", page=99)
    assert empty.tasks == [] and empty.total == 0 and empty.page == empty.pages == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sort": "id; DROP TABLE tasks"},
        {"search": None},
        {"search": "x" * 201},
        {"category": 1},
        {"page": 0},
        {"page": True},
        {"page": 1.5},
        {"page_size": 0},
        {"page_size": 101},
        {"page_size": False},
    ],
)
def test_invalid_query_arguments_never_reach_sql(monkeypatch, kwargs):
    query = Mock()
    monkeypatch.setattr(database, "get_task_page", query)
    with pytest.raises(ValueError):
        services.get_task_page("unused.db", **kwargs)
    query.assert_not_called()


def test_global_summary_overdue_rules_and_category_choices(db_path):
    today = date(2030, 1, 2)
    assert services.get_summary(db_path, today=today) == TaskSummary(0, 0, 0, 0)
    late = services.create_task(
        db_path, "Late", due_date=today - timedelta(days=1), category="Work"
    )
    due = services.create_task(db_path, "Today", due_date=today, category="Personal")
    done = services.create_task(db_path, "Done", due_date=today - timedelta(days=1), completed=True)
    services.create_task(db_path, "Unscheduled", category="Work")
    assert late.is_overdue(today)
    assert not due.is_overdue(today) and not done.is_overdue(today)
    assert services.get_summary(db_path, today=today) == TaskSummary(4, 3, 1, 1)
    assert services.list_categories(db_path) == ["Personal", "Work"]
    services.set_task_completed(db_path, late.id, True)
    assert services.get_summary(db_path, today=today) == TaskSummary(4, 2, 2, 0)


@pytest.mark.parametrize("task_id", [True, "1", None, 1.0])
def test_invalid_id_types_are_rejected(db_path, task_id):
    with pytest.raises(ValueError, match="ID"):
        services.get_task(db_path, task_id)
    with pytest.raises(ValueError, match="ID"):
        services.delete_task(db_path, task_id)
    with pytest.raises(ValueError, match="ID"):
        services.set_task_completed(db_path, task_id, True)


@pytest.mark.parametrize("version", [0, -1, True, None])
def test_invalid_revisions_are_rejected(db_path, version):
    task = services.create_task(db_path, "Keep")
    with pytest.raises(ValueError, match="Version"):
        services.update_task(db_path, replace(task, version=version))
    if version is not None:
        with pytest.raises(ValueError, match="Version"):
            services.delete_task(db_path, task.id, expected_version=version)


def test_query_indexes_exist_and_status_filter_uses_one(db_path):
    with database.get_connection(db_path) as connection:
        names = {row[1] for row in connection.execute("PRAGMA index_list(tasks)")}
        assert {
            "tasks_status_id",
            "tasks_category_status",
            "tasks_due",
            "tasks_created",
            "tasks_priority",
        } <= names
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE completed = 0 ORDER BY id LIMIT 10"
        ).fetchall()
        assert any("tasks_status_id" in row[3] for row in plan)


def test_default_summary_date_is_current_calendar_date(db_path):
    services.create_task(db_path, "Late", due_date=date.today() - timedelta(days=1))
    assert services.get_summary(db_path).overdue == 1
    with pytest.raises(ValueError):
        services.get_summary(db_path, today=datetime.now(UTC))
