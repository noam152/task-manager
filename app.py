"""Streamlit interface; all task operations go through the service layer."""

import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import streamlit as st

from task_manager import database, services
from task_manager.models import Priority

PRIORITIES = [priority.value for priority in Priority]


def notify(message: str, found: bool = True) -> None:
    """Keep feedback visible after rerunning with fresh database contents."""
    st.session_state.notice = ("success" if found else "warning", message)
    st.rerun()


def create_form(db_path: Path) -> None:
    if "new_priority" not in st.session_state:
        st.session_state.new_priority = Priority.MEDIUM.value
    if st.session_state.pop("reset_create", False):
        st.session_state.new_title = ""
        st.session_state.new_description = ""
        st.session_state.new_priority = Priority.MEDIUM.value
    st.subheader("Create a task")
    with st.form("create_task"):
        title = st.text_input("Title", key="new_title")
        description = st.text_area("Description", key="new_description")
        priority = st.selectbox("Priority", PRIORITIES, key="new_priority")
        submitted = st.form_submit_button("Create task", type="primary")
    if submitted:
        try:
            services.create_task(db_path, title, description, priority)
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
        st.session_state.loaded_edit_id = task_id
    st.subheader("Edit task")
    with st.form("edit_task"):
        title = st.text_input("Title", key="edit_title")
        description = st.text_area("Description", key="edit_description")
        priority = st.selectbox("Priority", PRIORITIES, key="edit_priority")
        submitted = st.form_submit_button("Save changes", type="primary")
    if submitted:
        try:
            found = services.update_task(
                db_path, replace(task, title=title, description=description, priority=priority)
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.edit_id = None
            notify("Task updated." if found else "This task no longer exists.", found)
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
        st.warning("Permanently delete this task? This cannot be undone.")
        st.text(task.title)
        confirm, cancel = st.columns(2)
        if confirm.button("Confirm deletion", key="confirm_delete", type="primary"):
            found = services.delete_task(db_path, task_id)
            st.session_state.delete_id = None
            if st.session_state.get("edit_id") == task_id:
                st.session_state.edit_id = None
            notify("Task deleted." if found else "This task no longer exists.", found)
        if cancel.button("Keep task", key="cancel_delete"):
            st.session_state.delete_id = None
            st.rerun()


def task_list(db_path: Path) -> None:
    st.subheader("Your tasks")
    status = st.selectbox("Filter by status", ["All", "Pending", "Completed"], key="status")
    tasks = services.list_tasks(db_path, status)
    if not tasks:
        st.info("No tasks yet. Create your first task above." if status == "All"
                else f"No {status.lower()} tasks.")
        return
    st.caption(f"{len(tasks)} task(s) shown")
    for task in tasks:
        with st.container(border=True):
            st.text(task.title)
            st.caption(f"{task.priority.value} priority · {'Completed' if task.completed else 'Pending'}")
            if task.description:
                st.text(task.description)
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
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="Task Manager", page_icon="✅", layout="centered")
    st.title("Task Manager")
    st.caption("Keep track of what matters, one task at a time.")
    # The optional override keeps automated tests away from the user's data.
    db_path = Path(os.environ.get(
        "TASK_MANAGER_DB_PATH", str(Path(__file__).resolve().parent / "data" / "tasks.db")
    ))
    try:
        database.initialize_database(db_path)
        notice = st.session_state.pop("notice", None)
        if notice:
            level, message = notice
            if level == "success":
                st.success(message)
            else:
                st.warning(message)
        create_form(db_path)
        delete_confirmation(db_path)
        edit_form(db_path)
        task_list(db_path)
    except (sqlite3.Error, OSError):
        st.error("Unable to access the task database. Check folder permissions and try again. "
                 "If the database is busy, wait a moment and retry.")


if __name__ == "__main__":
    main()
