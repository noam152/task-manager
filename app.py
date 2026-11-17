"""Streamlit interface; all task operations go through the service layer."""

import os
import sqlite3
from dataclasses import replace
from pathlib import Path
from datetime import date

import streamlit as st

from task_manager import database, services
from task_manager.models import Priority
from task_manager.errors import ConflictError, SchemaError

PRIORITIES = [priority.value for priority in Priority]
SORT_LABELS = {
    "Newest first": "created_desc", "Oldest first": "created_asc",
    "Priority": "priority", "Due date": "due_date",
}


def notify(message: str, found: bool = True) -> None:
    """Keep feedback visible after rerunning with fresh database contents."""
    st.session_state.notice = ("success" if found else "warning", message)
    st.rerun()


def change_page(delta: int) -> None:
    """Callbacks update pagination before the next full script execution."""
    st.session_state.page = max(1, st.session_state.get("page", 1) + delta)


def create_form(db_path: Path) -> None:
    if "new_priority" not in st.session_state:
        st.session_state.new_priority = Priority.MEDIUM.value
        st.session_state.new_due = None
        st.session_state.new_category = ""
    if st.session_state.pop("reset_create", False):
        st.session_state.new_title = ""
        st.session_state.new_description = ""
        st.session_state.new_priority = Priority.MEDIUM.value
        st.session_state.new_due = None
        st.session_state.new_category = ""
    st.subheader("Create a task")
    with st.form("create_task"):
        title = st.text_input("Title", key="new_title", max_chars=200)
        description = st.text_area("Description", key="new_description", max_chars=10000)
        priority = st.selectbox("Priority", PRIORITIES, key="new_priority")
        due_date = st.date_input("Due date (optional)", value=None, key="new_due")
        category = st.text_input("Category (optional)", key="new_category", max_chars=80)
        submitted = st.form_submit_button("Create task", type="primary")
    if submitted:
        try:
            services.create_task(db_path, title, description, priority, due_date=due_date, category=category)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.reset_create = True
            notify("Task created.")


def edit_form(db_path: Path) -> None:
    task_id = st.session_state.get("edit_id")
    if task_id is None:
        return
    task = services.get_task(db_path, task_id)
    if task is None:
        st.session_state.edit_id = None
        st.warning("This task no longer exists. The list has been refreshed.")
        return
    if st.session_state.get("loaded_edit_id") != task_id:
        st.session_state.edit_title = task.title
        st.session_state.edit_description = task.description
        st.session_state.edit_priority = task.priority.value
        st.session_state.edit_due = task.due_date
        st.session_state.edit_category = task.category
        st.session_state.edit_snapshot = task
        st.session_state.edit_conflict = False
        st.session_state.loaded_edit_id = task_id
    st.subheader("Edit task")
    with st.form("edit_task"):
        title = st.text_input("Title", key="edit_title")
        description = st.text_area("Description", key="edit_description")
        priority = st.selectbox("Priority", PRIORITIES, key="edit_priority")
        due_date = st.date_input("Due date (optional)", value=None, key="edit_due")
        category = st.text_input("Category (optional)", key="edit_category", max_chars=80)
        submitted = st.form_submit_button("Save changes", type="primary")
    if submitted:
        try:
            found = services.update_task(
                db_path, replace(st.session_state.edit_snapshot, title=title,
                                 description=description, priority=priority,
                                 due_date=due_date, category=category)
            )
        except ValueError as error:
            st.error(str(error))
        except ConflictError:
            st.session_state.edit_conflict = True
        else:
            st.session_state.edit_id = None
            notify("Task updated." if found else "This task no longer exists.", found)
    if st.session_state.get("edit_conflict"):
        st.warning("This task changed in another session. Your draft was not saved. "
                   "Copy any text you need, then reload the latest task.")
        if st.button("Reload latest task", key="reload_edit"):
            st.session_state.loaded_edit_id = None
            st.rerun()
    if st.button("Cancel editing", key="cancel_edit"):
        st.session_state.edit_id = None
        st.rerun()


def delete_confirmation(db_path: Path) -> None:
    task_id = st.session_state.get("delete_id")
    if task_id is None:
        return
    task = services.get_task(db_path, task_id)
    if task is None:
        st.session_state.delete_id = None
        st.warning("This task no longer exists. Nothing was deleted.")
        return
    with st.container(border=True):
        snapshot = st.session_state.delete_snapshot
        if task.version != snapshot.version:
            st.warning("This task changed since you selected it. Review the latest task before deleting.")
            st.text(task.title)
            if st.button("Review latest task", key="review_delete"):
                st.session_state.delete_snapshot = task
                st.rerun()
            if st.button("Keep task", key="cancel_delete"):
                st.session_state.delete_id = None
                st.rerun()
            return
        st.warning("Permanently delete this task? This cannot be undone.")
        st.text(task.title)
        st.caption(f"{task.priority.value} priority · {'Completed' if task.completed else 'Pending'}")
        if task.description:
            st.text(task.description)
        confirm, cancel = st.columns(2)
        if confirm.button("Confirm deletion", key="confirm_delete", type="primary"):
            try:
                found = services.delete_task(db_path, task_id, expected_version=snapshot.version)
            except ConflictError as error:
                st.warning(str(error))
            else:
                st.session_state.delete_id = None
                if st.session_state.get("edit_id") == task_id:
                    st.session_state.edit_id = None
                notify("Task deleted." if found else "This task no longer exists.", found)
        if cancel.button("Keep task", key="cancel_delete"):
            st.session_state.delete_id = None
            st.rerun()


def task_list(db_path: Path) -> None:
    st.subheader("Your tasks")
    search = st.text_input("Search title or description", key="search", max_chars=200)
    status_column, category_column, sort_column, size_column = st.columns(4)
    status = status_column.selectbox("Filter by status", ["All", "Pending", "Completed"], key="status")
    categories = services.list_categories(db_path)
    if st.session_state.get("category_filter") not in [None, "", *categories]:
        st.session_state.category_filter = None
    category = category_column.selectbox(
        "Category", [None, "", *categories], key="category_filter",
        format_func=lambda value: "All categories" if value is None else value or "Uncategorized",
    )
    sort = sort_column.selectbox("Sort by", list(SORT_LABELS), key="sort")
    page_size = size_column.selectbox("Tasks per page", [10, 25, 50], key="page_size")
    signature = (status, search, category, sort, page_size)
    if st.session_state.get("query_signature") != signature:
        st.session_state.page = 1
        st.session_state.query_signature = signature
    result = services.get_task_page(db_path, status, search=search, category=category,
                                   sort=SORT_LABELS[sort], page=st.session_state.page,
                                   page_size=page_size)
    st.session_state.page = result.page
    if not result.tasks:
        if search.strip() or category is not None:
            st.info("No tasks match these filters. Try a different search or category.")
        else:
            st.info("No tasks yet. Create your first task above." if status == "All"
                    else f"No {status.lower()} tasks.")
        return
    st.caption(f"{result.total} matching task(s) · Page {result.page} of {result.pages}")
    for task in result.tasks:
        with st.container(border=True):
            st.text(task.title)
            st.caption(f"{task.priority.value} priority · {'Completed' if task.completed else 'Pending'}")
            if task.description:
                st.text(task.description)
            details = []
            if task.category:
                details.append(f"Category: {task.category}")
            if task.due_date:
                details.append(f"Due {task.due_date.isoformat()}")
                if task.is_overdue(date.today()):
                    details.append("Overdue")
            if task.created_at:
                details.append(f"Created {task.created_at:%Y-%m-%d %H:%M} UTC")
            if details:
                st.caption(" · ".join(details))
            edit, complete, delete = st.columns(3)
            if edit.button("Edit", key=f"edit_{task.id}"):
                st.session_state.edit_id = task.id
                st.session_state.loaded_edit_id = None
                st.rerun()
            if complete.button("Reopen" if task.completed else "Complete", key=f"complete_{task.id}"):
                found = services.set_task_completed(db_path, task.id, not task.completed)
                message = "Task reopened." if task.completed else "Task completed."
                notify(message if found else "This task no longer exists.", found)
            if delete.button("Delete", key=f"delete_{task.id}"):
                st.session_state.delete_id = task.id
                st.session_state.delete_snapshot = task
                st.rerun()
    previous, next_page = st.columns(2)
    previous.button("Previous page", key="previous_page", disabled=result.page == 1,
                    on_click=change_page, args=(-1,))
    next_page.button("Next page", key="next_page", disabled=result.page == result.pages,
                     on_click=change_page, args=(1,))


def main() -> None:
    st.set_page_config(page_title="Task Manager", page_icon="✅", layout="wide")
    st.title("Task Manager")
    st.caption("A clear view of what is next. Your tasks stay on this device.")
    # The optional override keeps automated tests away from the user's data.
    db_path = Path(os.environ.get(
        "TASK_MANAGER_DB_PATH", str(Path(__file__).resolve().parent / "data" / "tasks.db")
    ))
    try:
        with st.spinner("Loading your workspace..."):
            database.initialize_database(db_path)
            summary = services.get_summary(db_path)
        for column, label, value in zip(st.columns(4),
                                        ["Total", "Pending", "Completed", "Overdue"],
                                        [summary.total, summary.pending, summary.completed, summary.overdue]):
            column.metric(label, value)
        # Clicking already causes a full rerun; no early rerun is needed.
        st.button("Refresh tasks", key="refresh")
        notice = st.session_state.pop("notice", None)
        if notice:
            level, message = notice
            if level == "success":
                st.success(message)
            else:
                st.warning(message)
        with st.sidebar:
            create_form(db_path)
        delete_confirmation(db_path)
        edit_form(db_path)
        task_list(db_path)
    except SchemaError as error:
        st.error(str(error))
    except (sqlite3.Error, OSError):
        st.error("Unable to access the task database. Check folder permissions and try again. "
                 "If the database is busy, wait a moment and retry.")


if __name__ == "__main__":
    main()
