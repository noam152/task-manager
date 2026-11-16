# Task Manager

A beginner-friendly task management web application planned with Python,
Streamlit, SQLite, and pytest.

## Current status

The Task model and SQLite persistence layer are implemented and tested. Services
and the Streamlit interface remain placeholders. No application database is
created automatically. Automated GitHub checks will be configured in a later step.

Planned features:

- Create, edit, and delete tasks.
- Complete and reopen tasks.
- Assign Low, Medium, or High priority.
- Filter by All, Pending, or Completed status.
- Save tasks locally with SQLite.

The initial application will use one shared local task list without user accounts.

## Development setup

Use Python 3.12. Initialization was verified with Python 3.12.10 on Windows.
Run the following commands from the project root.

### Windows PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Using the environment's Python directly avoids needing to activate it or change
PowerShell execution policies. The `python` command is sufficient; the Windows
`py` launcher is not required.

### macOS and Linux

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

`requirements.txt` contains Streamlit, the sole direct runtime dependency.
`requirements-dev.txt` includes it and adds pytest. Direct versions are pinned
to keep the initial setup consistent; transitive dependencies are resolved by pip.
SQLite uses Python's built-in `sqlite3` module and needs no pip dependency.

## Basic checks

On Windows:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import task_manager; import task_manager.models; import task_manager.database; import task_manager.services"
.\.venv\Scripts\python.exe -m pytest
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

`pip check` checks installed dependency compatibility. The import command checks
that the package is available from the project root. `pytest.ini` sets the test
directory and adds the project root to pytest's import path.

Run only the persistence tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database.py
```

All database tests use pytest's temporary directories, never an application
database. Service and interface test modules remain placeholders.

## Running the application later

After the interface is implemented, the Windows launch command will be:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For now, `app.py` is only a placeholder and will display no application interface.

## Project layout

```text
task-manager/
|-- app.py                    # Future Streamlit interface
|-- task_manager/
|   |-- __init__.py           # Importable application package
|   |-- models.py             # Task dataclass and Priority enum
|   |-- database.py           # SQLite connections, schema, and CRUD
|   `-- services.py           # Future validation and task operations
|-- tests/
|   |-- conftest.py           # Future shared fixtures
|   |-- test_database.py      # Persistence and connection-management tests
|   |-- test_services.py      # Future behavior tests
|   `-- test_app.py           # Future interface tests
|-- .github/workflows/
|   `-- .gitkeep              # Preserves the future CI directory
|-- .gitignore               # Excludes local/generated files and secrets
|-- pytest.ini               # Test discovery and package import settings
|-- requirements.txt         # Direct runtime dependencies
|-- requirements-dev.txt     # Runtime and testing dependencies
`-- README.md                # Setup, scope, and project guide
```

## Persistence API

`Task` is a dataclass with `id`, `title`, `description`, `priority`, and
`completed` fields. SQLite assigns IDs when creating tasks. Description defaults
to an empty string, priority to `Priority.MEDIUM`, and completion to `False`.
`Priority` is a string enum defining `Low`, `Medium`, and `High` in display order.

All persistence functions require an explicit file-backed path (`str` or `Path`).
The future UI can choose `data/tasks.db`; tests always choose temporary paths.
Importing the package does not create directories or open a database.

| Function | Behavior |
| --- | --- |
| `initialize_database(db_path)` | Creates parent directories and the table; safe to repeat without losing tasks. |
| `create_task(db_path, title, description="", priority=Priority.MEDIUM, completed=False)` | Inserts and returns a `Task` with its generated ID. |
| `get_task(db_path, task_id)` | Returns a `Task`, or `None` for a missing ID. |
| `list_tasks(db_path)` | Returns tasks in ascending ID order, or an empty list. |
| `update_task(db_path, task)` | Replaces editable fields by ID; returns `True` if found, including unchanged values, or `False` if missing. |
| `delete_task(db_path, task_id)` | Returns `True` if deleted, or `False` if missing or already deleted. |
| `get_connection(db_path)` | Context manager that commits on success, rolls back on error, and always closes the connection. |

Call initialization before CRUD operations. Each call uses a new connection,
so per-connection `:memory:` databases are unsuitable for this API. SQLite errors
propagate to the caller, including `sqlite3.IntegrityError` for constraint
violations. The schema enforces non-null fields, supported priorities, and
completion values of 0 or 1. User-supplied query values are parameterized.
Blank-title checks and other business validation belong to the future services
layer; the database does not trim or reject blank text. Initialization creates
the initial schema; it does not migrate an incompatible existing schema.

## Git and GitHub

The primary branch is `main`. Project initialization does not create a commit,
configure a remote, or publish anything.

Keep commits small and include relevant tests with each feature. Before committing,
review `git status` and the staged diff. Virtual environments, database files,
caches, and common secret files are ignored. Git ignore patterns cannot detect
secrets embedded in source files, so review those files too.

Before GitHub publication, choose a license, finish the setup documentation,
implement a pytest workflow, and verify the full test suite. Add a remote and
push only when publication is authorized.
