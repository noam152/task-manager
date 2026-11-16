# Task Manager

A beginner-friendly task management web application planned with Python,
Streamlit, SQLite, and pytest.

## Current status

Only project initialization is complete. Python modules and test modules are
placeholders. There is no Streamlit interface, task behavior, database schema,
or database file yet. Automated GitHub checks will be configured in a later step.

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

At this stage pytest reports **no tests ran** and exits with code **5**, because
test modules contain no test functions. This is expected during initialization;
behavior tests will accompany later implementation steps.

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
|   |-- models.py             # Future task model and allowed values
|   |-- database.py           # Future SQLite storage operations
|   `-- services.py           # Future validation and task operations
|-- tests/
|   |-- conftest.py           # Future shared fixtures
|   |-- test_database.py      # Future persistence tests
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

The future database will live at `data/tasks.db`; that directory and database
will be created when persistence is implemented. Tests will use isolated
temporary databases.

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
