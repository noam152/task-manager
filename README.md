# Task Manager V2

A local task dashboard built with Python 3.12, Streamlit, SQLite and pytest.
Create, edit, complete, reopen and delete tasks. Organize them with priorities,
categories and optional due dates. Search, filter, sort and browse bounded pages.

## Setup and run

From the project root in Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

On macOS/Linux with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

Open the Local URL printed in the terminal (normally `http://localhost:8501`).
Stop with Ctrl+C. No account, API key or separate SQLite installation is needed.
The lock file pins runtime and development dependencies; `requirements.txt` and
`requirements-dev.txt` declare direct dependencies for deliberate updates.

The database defaults to `data/tasks.db` beside `app.py`. An optional override:

```powershell
$env:TASK_MANAGER_DB_PATH = "C:\path\to\tasks.db"
```

Unset with `Remove-Item Env:TASK_MANAGER_DB_PATH`. Relative overrides resolve from
the working directory. Databases, environments, caches, logs, coverage output and
common secret files are Git-ignored. Do not put secrets in source files.

## Dashboard

- Create tasks in the sidebar. Medium is the default priority. Successful creation
  clears the form; validation errors preserve input.
- Summary metrics are **global**, independent of filters. A pending task is overdue
  when its due date is before the server's calendar date. Due today is not overdue.
  Creation times are stored/displayed in UTC.
- Search title/description, filter by status/category and sort by priority, due date
  (unscheduled last), newest or oldest. Search treats `%` and `_` literally.
- Pages show 10, 25 or 50 tasks. Filters reset the page; deletions clamp empty pages.
- Edit and save, or cancel. A stale draft is retained but not saved. Copy any needed
  text, choose **Reload latest task**, review the current data, then edit again.
- Complete/reopen changes only completion. Delete requires confirmation; a changed
  target must be reviewed again. There is no recycle bin.
- **Refresh tasks** reloads data. Lock failures show a retry message; detailed
  database failures go to server logs, not the browser.

## Existing data and migrations

**Before first launching V2**, stop all instances and copy `data/tasks.db` to a
safe backup location. Initialization creates directories and applies numbered
migrations transactionally. Original IDs and task content are preserved. Since V1
did not record creation times, migrated tasks receive the upgrade timestamp.
Future/unknown schemas are rejected rather than overwritten.

Development/test runs use isolated temporary databases and do not migrate local
user data. Migration happens when you launch the app. There is no automatic
downgrade: stop the app and restore the pre-upgrade backup with the old code.
Do not run V1 against V2 data; it lacks revision checks. For live backups use
SQLite's backup API instead of copying an active file.

## Architecture and service API

```text
app.py                         Streamlit dashboard, forms and session drafts
task_manager/models.py         Task, Priority, TaskPage and TaskSummary
task_manager/services.py       Validation and business operations
task_manager/database.py       Parameterized SQL, transactions and pagination
task_manager/migrations.py     Numbered additive migrations
task_manager/errors.py         ConflictError and SchemaError
tests/                         Database, concurrency, service and AppTest tests
pyproject.toml                 Ruff and branch-coverage configuration
.github/workflows/tests.yml    Lint, format, tests and coverage gates
```

All backend operations take an explicit file-backed path. First call
`database.initialize_database(path)`. Imports have no database side effects.

| Service | Contract |
| --- | --- |
| `create_task(path, title, description="", priority=Priority.MEDIUM, completed=False, *, due_date=None, category="")` | Returns a persisted `Task`. |
| `get_task(path, task_id)` | Returns `Task` or `None` if missing. |
| `update_task(path, task)` | Replaces editable fields, increments revision; False if missing, `ConflictError` if stale. Input is not mutated. Reload after saving. |
| `set_task_completed(path, task_id, completed)` | Atomic completion update, False if missing. Repeating a state does not advance revision. |
| `delete_task(path, task_id, *, expected_version=None)` | False if missing. The UI supplies a revision; omission is for intentional administrative deletion. |
| `list_tasks(path, status="All", *, search="", category=None, sort="id")` | Unbounded compatibility/export API; use pages for dashboards. |
| `get_task_page(path, status="All", *, search="", category=None, sort="id", page=1, page_size=10)` | A `TaskPage` with tasks, count, clamped page and page size. |
| `get_summary(path, *, today=None)` / `list_categories(path)` | Global counts / distinct nonempty category labels. |

Invalid input raises `ValueError` before SQL access, even for missing IDs. SQLite
errors propagate to the UI boundary. Titles are trimmed, required and limited to
200 characters. Descriptions preserve whitespace (maximum 10000). Categories are
trimmed, case-sensitive labels up to 80 characters; empty means uncategorized.
Priorities accept enum members or exact Low/Medium/High labels. Due dates are
`datetime.date` or `None`, not strings/timestamps. Completion must be a boolean.
Duplicate titles and past due dates are allowed. Sort keys are `id`, `priority`,
`due_date`, `created_desc`, `created_asc`. Valid unchanged edits advance revision.

See [architecture and operations](docs/ARCHITECTURE.md) for transaction details,
index decisions, backup guidance and deployment alternatives.

## Tests and quality

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing --cov-report=xml
git diff --check
```

On macOS/Linux replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
Target a file by appending e.g. `tests/test_integrity.py` to the pytest command.
For HTML coverage use `python -m pytest --cov --cov-report=html` in the virtual
environment; reports go to ignored `htmlcov/`. All integration tests/AppTest use
temporary paths, never the default user database.

CI runs on main pushes and pull requests targeting main, with Ubuntu/Python 3.12.
It installs `requirements-dev.lock`, runs Ruff lint/format, and tests with branch
measurement and a **90% combined coverage floor**. Permissions are read-only,
actions use immutable SHAs, and no deployment or repository write is performed.

For dependency updates, use a **clean Python 3.12 environment**, install
`requirements-dev.txt`, run all checks, then regenerate the lock with
`python -m pip freeze`. Review every changed pin, including transitive packages,
and verify Ubuntu CI before adoption. The lock is version-pinned, not a hash lock
or vulnerability-audit guarantee.

## Limitations

This is a local/small trusted-team app, not a public multi-tenant service. There
is no authentication, ownership, encryption at rest, reminder delivery or audit
history. Everyone who can reach the server shares the same task list. Bind to
loopback and protect OS/database access; do not expose it publicly as-is.

SQLite supports one host and modest writes; writers serialize and locks may time
out after five seconds. Substring search scans candidates and deep OFFSET pages
cost more. SQLite LIKE is ASCII case-insensitive, not full Unicode case folding.
Categories are single labels, not many-to-many tags. Refresh is manual and due
dates use the server's date, not each browser's timezone.

FastAPI/REST needs independent clients; authentication/ownership is needed before
untrusted users; PostgreSQL needs multi-host or sustained concurrent writes.
Docker is optional packaging. Costs and deployment requirements are evaluated in
[architecture notes](docs/ARCHITECTURE.md#deployment-and-possible-expansion);
none is introduced automatically.

## License

[MIT](LICENSE), selected by the project owner.
