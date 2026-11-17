"""Exercise the real Streamlit app with isolated temporary database paths."""

import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from task_manager import database, services
from task_manager.models import Priority

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def ui(tmp_path, monkeypatch):
    path = tmp_path / "data" / "tasks.db"
    monkeypatch.setenv("TASK_MANAGER_DB_PATH", str(path))
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert not app.exception
    return app, path


def button(app, label):
    return next(item for item in app.button if item.label == label)


def create_task(app, title="Write tests", description="Cover the UI", priority="High"):
    app.text_input(key="new_title").input(title)
    app.text_area(key="new_description").input(description)
    app.selectbox(key="new_priority").select(priority)
    button(app, "Create task").click().run()
    assert not app.exception


def visible_text(app):
    return [item.value for item in app.text]


def test_startup_initializes_nested_database_and_shows_empty_state(ui):
    app, path = ui
    assert path.is_file()
    assert "No tasks yet" in app.info[0].value
    assert services.list_tasks(path) == []
    app.run()
    assert not app.exception
    assert services.list_tasks(path) == []


def test_create_displays_details_and_persists_in_fresh_session(ui):
    app, path = ui
    create_task(app, "  Write tests  ")
    assert app.success[0].value == "Task created."
    assert "Write tests" in visible_text(app)
    assert "Cover the UI" in visible_text(app)
    assert any("High priority" in item.value and "Pending" in item.value for item in app.caption)
    task = services.list_tasks(path)[0]
    assert task.title == "Write tests"
    assert task.priority is Priority.HIGH
    assert app.text_input(key="new_title").value == ""
    fresh = AppTest.from_file(str(APP_PATH)).run()
    assert not fresh.exception
    assert "Write tests" in visible_text(fresh)


@pytest.mark.parametrize("priority", ["Low", "High"])
def test_priority_default_and_form_reset_have_no_state_warning(ui, monkeypatch, priority):
    from streamlit.elements.lib import policies

    # Streamlit emits this warning once per process; earlier tests must not hide it.
    monkeypatch.setattr(policies, "_shown_default_value_warning", False)
    app, path = ui
    assert app.selectbox(key="new_priority").value == "Medium"
    app.selectbox(key="new_priority").select(priority).run()
    assert app.selectbox(key="new_priority").value == priority
    assert not app.warning

    create_task(app, priority=priority)
    assert not app.warning
    assert app.text_input(key="new_title").value == ""
    assert app.text_area(key="new_description").value == ""
    assert app.selectbox(key="new_priority").value == "Medium"
    app.run()
    assert not app.exception
    assert not app.warning
    assert app.selectbox(key="new_priority").value == "Medium"

    app.text_input(key="new_title").input("Use the default")
    button(app, "Create task").click().run()
    assert not app.exception
    assert not app.warning
    assert [task.priority for task in services.list_tasks(path)] == [
        Priority(priority), Priority.MEDIUM
    ]


@pytest.mark.parametrize("title", ["", " \t "])
def test_invalid_creation_shows_validation_and_preserves_input(ui, title):
    app, path = ui
    create_task(app, title)
    assert "Title" in app.error[0].value
    assert app.text_area(key="new_description").value == "Cover the UI"
    assert services.list_tasks(path) == []


def test_edit_changes_details_and_preserves_completion(ui):
    app, path = ui
    task = services.create_task(path, "Original", completed=True)
    app.run().button(key=f"edit_{task.id}").click().run()
    app.text_input(key="edit_title").input("Edited")
    app.text_area(key="edit_description").input("New details")
    app.selectbox(key="edit_priority").select("Low")
    button(app, "Save changes").click().run()
    assert not app.exception
    assert app.success[0].value == "Task updated."
    edited = services.get_task(path, task.id)
    assert (edited.title, edited.description, edited.priority, edited.completed) == (
        "Edited", "New details", Priority.LOW, True
    )
    assert "Edited" in visible_text(app)
    assert not any(item.key == "edit_title" for item in app.text_input)


def test_invalid_edit_and_cancel_do_not_change_task(ui):
    app, path = ui
    task = services.create_task(path, "Keep", "Details")
    app.run().button(key=f"edit_{task.id}").click().run()
    app.text_input(key="edit_title").input(" ")
    button(app, "Save changes").click().run()
    assert "Title" in app.error[0].value
    assert services.get_task(path, task.id) == task
    app.button(key="cancel_edit").click().run()
    assert not app.exception
    assert services.get_task(path, task.id) == task
    assert not any(item.key == "edit_title" for item in app.text_input)


def test_complete_reopen_and_filter_update_visible_tasks(ui):
    app, path = ui
    first = services.create_task(path, "First")
    second = services.create_task(path, "Second", completed=True)
    app.run().selectbox(key="status").select("Pending").run()
    assert "First" in visible_text(app) and "Second" not in visible_text(app)
    app.button(key=f"complete_{first.id}").click().run()
    assert services.get_task(path, first.id).completed is True
    assert app.success[0].value == "Task completed."
    assert "No pending tasks" in app.info[0].value
    app.selectbox(key="status").select("Completed").run()
    assert "First" in visible_text(app) and "Second" in visible_text(app)
    app.button(key=f"complete_{second.id}").click().run()
    assert services.get_task(path, second.id).completed is False
    assert app.success[0].value == "Task reopened."
    assert "Second" not in visible_text(app)
    app.selectbox(key="status").select("All").run()
    assert "First" in visible_text(app) and "Second" in visible_text(app)
    assert not app.exception


def test_delete_requires_confirmation_and_can_be_cancelled(ui):
    app, path = ui
    task = services.create_task(path, "Delete me")
    app.run().button(key=f"delete_{task.id}").click().run()
    assert services.get_task(path, task.id) == task
    assert "cannot be undone" in app.warning[0].value
    app.button(key="cancel_delete").click().run()
    assert services.get_task(path, task.id) == task
    assert not any(item.key == "confirm_delete" for item in app.button)
    app.button(key=f"delete_{task.id}").click().run()
    app.button(key="confirm_delete").click().run()
    assert not app.exception
    assert app.success[0].value == "Task deleted."
    assert services.get_task(path, task.id) is None
    assert "No tasks yet" in app.info[0].value


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_selected_task_removed_externally_shows_warning(ui, action):
    app, path = ui
    task = services.create_task(path, "Gone")
    app.run().button(key=f"{action}_{task.id}").click().run()
    services.delete_task(path, task.id)
    app.run()
    assert not app.exception
    assert "no longer exists" in app.warning[0].value
    assert "No tasks yet" in app.info[0].value


def test_missing_task_during_completion_is_not_reported_as_success(ui, monkeypatch):
    app, path = ui
    task = services.create_task(path, "Task")
    app.run()
    monkeypatch.setattr(services, "set_task_completed", Mock(return_value=False))
    app.button(key=f"complete_{task.id}").click().run()
    assert not app.exception
    assert "no longer exists" in app.warning[0].value
    assert not app.success


def test_database_error_shows_friendly_message(ui, monkeypatch):
    app, _ = ui
    monkeypatch.setattr(database, "initialize_database", Mock(
        side_effect=sqlite3.OperationalError("internal details")
    ))
    app.run()
    assert not app.exception
    assert "Unable to access" in app.error[0].value
    assert "internal details" not in app.error[0].value


def test_due_date_category_form_reset_and_summary_metrics(ui):
    app, path = ui
    yesterday = date.today() - timedelta(days=1)
    app.date_input(key="new_due").set_value(yesterday)
    app.text_input(key="new_category").input("Work")
    create_task(app)
    task = services.list_tasks(path)[0]
    assert task.due_date == yesterday and task.category == "Work"
    assert app.date_input(key="new_due").value is None
    assert app.text_input(key="new_category").value == ""
    assert {item.label: item.value for item in app.metric} == {
        "Total": "1", "Pending": "1", "Completed": "0", "Overdue": "1"
    }
    assert any("Overdue" in item.value and yesterday.isoformat() in item.value for item in app.caption)
    assert not app.exception and not app.warning


def test_editor_saves_due_date_and_category(ui):
    app, path = ui
    task = services.create_task(path, "Plan", due_date=date.today(), category="Work")
    app.run().button(key=f"edit_{task.id}").click().run()
    app.date_input(key="edit_due").set_value(None)
    app.text_input(key="edit_category").input("Personal")
    button(app, "Save changes").click().run()
    updated = services.get_task(path, task.id)
    assert updated.due_date is None and updated.category == "Personal"
    assert updated.created_at == task.created_at
    assert not app.exception


def test_stale_editor_preserves_draft_until_explicit_reload(ui):
    app, path = ui
    task = services.create_task(path, "Original")
    app.run().button(key=f"edit_{task.id}").click().run()
    services.update_task(path, replace(task, title="Other session"))
    services.set_task_completed(path, task.id, True)
    app.text_input(key="edit_title").input("My draft")
    button(app, "Save changes").click().run()
    assert not app.exception
    assert "draft was not saved" in app.warning[0].value
    assert app.text_input(key="edit_title").value == "My draft"
    assert services.get_task(path, task.id).title == "Other session"
    app.button(key="reload_edit").click().run()
    assert app.text_input(key="edit_title").value == "Other session"
    app.text_input(key="edit_title").input("Reviewed edit")
    button(app, "Save changes").click().run()
    current = services.get_task(path, task.id)
    assert current.title == "Reviewed edit" and current.completed is True
    assert app.success[0].value == "Task updated."


def test_changed_delete_target_requires_review_and_reconfirmation(ui):
    app, path = ui
    task = services.create_task(path, "Original")
    app.run().button(key=f"delete_{task.id}").click().run()
    services.update_task(path, replace(task, title="Changed elsewhere"))
    app.button(key="confirm_delete").click().run()
    assert services.get_task(path, task.id) is not None
    assert "Review the latest" in app.warning[0].value
    assert not any(item.key == "confirm_delete" for item in app.button)
    app.button(key="review_delete").click().run()
    assert "Changed elsewhere" in visible_text(app)
    app.button(key="confirm_delete").click().run()
    assert services.get_task(path, task.id) is None
    assert not app.exception


def test_delete_conflict_between_display_and_write_is_caught(ui, monkeypatch):
    app, path = ui
    task = services.create_task(path, "Keep")
    app.run().button(key=f"delete_{task.id}").click().run()
    original_delete = services.delete_task

    def concurrent_delete(db_path, task_id, **kwargs):
        services.set_task_completed(db_path, task_id, True)
        return original_delete(db_path, task_id, **kwargs)

    monkeypatch.setattr(services, "delete_task", concurrent_delete)
    app.button(key="confirm_delete").click().run()
    assert not app.exception
    assert any("changed" in item.value for item in app.warning)
    assert services.get_task(path, task.id).completed is True


def test_dashboard_pagination_search_and_filter_reset(ui):
    app, path = ui
    tasks = [services.create_task(path, f"Task {i}") for i in range(12)]
    app.run()
    assert len([item for item in app.button if str(item.key).startswith("edit_")]) == 10
    assert app.button(key="previous_page").disabled
    app.button(key="next_page").click().run()
    assert tasks[0].title in visible_text(app) and tasks[-1].title not in visible_text(app)
    assert app.button(key="next_page").disabled
    app.text_input(key="search").input("Task 11").run()
    assert tasks[-1].title in visible_text(app)
    assert tasks[0].title not in visible_text(app)
    assert any("Page 1 of 1" in item.value for item in app.caption)
    app.text_input(key="search").input("No match").run()
    assert "No tasks match" in app.info[0].value
    assert not app.exception


def test_category_filter_and_sorting(ui):
    app, path = ui
    low = services.create_task(path, "Low", category="Work", priority=Priority.LOW)
    high = services.create_task(path, "High", category="Work", priority=Priority.HIGH)
    personal = services.create_task(path, "Other", category="Personal")
    app.run().selectbox(key="category_filter").select("Work").run()
    app.selectbox(key="sort").select("Priority").run()
    texts = visible_text(app)
    assert texts.index(high.title) < texts.index(low.title)
    assert personal.title not in texts
    services.delete_task(path, low.id)
    services.delete_task(path, high.id)
    app.run()
    assert not app.exception
    assert personal.title in visible_text(app)


def test_previous_page_navigation_and_refresh_preserve_filters(ui):
    app, path = ui
    for i in range(11):
        services.create_task(path, f"Task {i}")
    app.run().button(key="next_page").click().run()
    app.button(key="previous_page").click().run()
    app.button(key="refresh").click().run()
    assert not app.exception
    assert any("Page 1 of 2" in item.value for item in app.caption), [item.value for item in app.caption]
