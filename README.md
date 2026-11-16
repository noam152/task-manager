# Task Manager

A beginner-friendly task management web application planned with Python,
Streamlit, SQLite, and pytest.

## Current status

The Task model, SQLite persistence layer, and service layer are implemented and
tested. The Streamlit interface remains a placeholder. No application database is
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

Run only the service tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_services.py
```

Database and service integration tests use pytest's temporary directories, never
an application database. Service unit tests use mocks to verify validation before
database access. The interface test module remains a placeholder.

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
|   `-- services.py           # Validation, task operations, and status filtering
|-- tests/
|   |-- conftest.py           # Future shared fixtures
|   |-- test_database.py      # Persistence and connection-management tests
|   |-- test_services.py      # Service unit and integration tests
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
Blank-title checks and other business validation belong to the services
layer; the database does not trim or reject blank text. Initialization creates
the initial schema; it does not migrate an incompatible existing schema.

## Service API

Use `task_manager.services` for validated application operations. Its functions
require the same explicit file-backed database path as persistence. Initialize
the database through `database.initialize_database(db_path)` before using it;
services do not initialize databases implicitly or contain SQL.

| Function | Behavior |
| --- | --- |
| `create_task(db_path, title, description="", priority=Priority.MEDIUM, completed=False)` | Validates and returns a new persisted `Task`. |
| `get_task(db_path, task_id)` | Returns a task or `None` for a missing ID. |
| `update_task(db_path, task)` | Validates and replaces all editable fields; returns `False` if missing, otherwise `True`, even when unchanged. Does not mutate the supplied task. |
| `set_task_completed(db_path, task_id, completed)` | Pass `True` to complete or `False` to reopen. Preserves the other fields. Returns `False` if missing; repeating the current state returns `True`. |
| `delete_task(db_path, task_id)` | Returns `True` if deleted, or `False` if missing/already deleted. |
| `list_tasks(db_path, status="All")` | Accepts exactly `All`, `Pending`, or `Completed`, preserves ascending ID order, and returns an empty list when nothing matches. |

Creation and updates require a string title containing non-whitespace characters.
Leading/trailing title whitespace is stripped; internal whitespace and Unicode
are preserved. Duplicate titles are allowed. Descriptions must be strings;
empty descriptions are allowed and their whitespace is preserved. Priorities
accept a `Priority` member or its exact label (`Low`, `Medium`, or `High`), without
case conversion or whitespace trimming. Completion values must be actual booleans,
not integers or strings.

Invalid fields or status filters raise `ValueError` before database access.
Updates validate input even when the supplied ID does not exist. For valid input,
missing IDs follow the database API's `None`/`False` behavior. Database exceptions
propagate unchanged; they are not converted into validation errors.

Updates accept the full `Task`, matching the existing database API. Use
`dataclasses.replace` to preserve fields that are not being edited:

```python
from dataclasses import replace
from task_manager import services
from task_manager.models import Priority

# db_path must refer to an explicitly initialized database.
task = services.create_task(db_path, "  Write tests  ", priority=Priority.HIGH)
services.update_task(db_path, replace(task, description="Cover edge cases"))
services.set_task_completed(db_path, task.id, True)
completed_tasks = services.list_tasks(db_path, "Completed")
services.set_task_completed(db_path, task.id, False)  # Reopen the task.
```

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
