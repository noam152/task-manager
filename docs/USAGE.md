# Usage and operations

[Project overview and quick start](../README.md) · [Architecture](ARCHITECTURE.md) ·
[Development](DEVELOPMENT.md)

## Dashboard

Create tasks in the sidebar. Medium is the default priority; description, due date,
and category are optional. Successful creation clears the form. Validation errors
preserve your input so you can correct it.

The summary shows **global** total, pending, completed, and overdue counts,
independent of the current filters. A pending task is overdue when its due date is
before the server's calendar date. Tasks due today are not overdue. Creation times
are stored and displayed in UTC.

Search titles and descriptions, filter by status and category, and sort by priority,
due date, newest, or oldest. Tasks without a due date appear last when sorting by
due date. Search treats `%` and `_` literally. Pages show 10, 25, or 50 tasks;
changing filters or page size resets to page one. Deletions clamp the page to an
available result instead of leaving an inaccessible page.

Choose **Edit**, then **Save changes** or **Cancel editing**. If another session
has changed the task, your draft remains visible but is not saved. Copy any text
you need, select **Reload latest task**, review the current values, and edit again.

**Complete** and **Reopen** change only completion state. **Delete** requires
**Confirm deletion**; **Keep task** cancels. A task changed since selection must
be reviewed again before confirmation. There is no recycle bin.

**Refresh tasks** reloads current data. There is no automatic background refresh.

## Capturing a dashboard screenshot

The README screenshot is pending. To provide a real capture:

1. Start the application using the [quick-start instructions](../README.md#quick-start).
   If your usual database contains personal information, first select a separate
   demo database using [database configuration](#database-configuration).
2. Add only non-sensitive sample tasks. Show the main dashboard with its summary,
   filters, and task cards; close any edit or deletion dialogs.
3. Capture the dashboard from the browser. On Windows, use Win+Shift+S and crop out
   unrelated windows, browser tabs, and personal details. Check the image before sharing.
4. Save the capture as `docs/images/dashboard.png`, relative to the repository root,
   or attach the PNG for it to be added there. Do not use a mockup or placeholder.

Once the PNG exists, replace the README's pending notice with a Markdown image
using `docs/images/dashboard.png` and descriptive alt text. Until then, omit the
image reference so the README has no broken image.

## Database configuration

The default database is `data/tasks.db`, resolved relative to `app.py`. The app
creates its parent directory and initializes or migrates the schema on startup.
Tasks persist across browser refreshes and server restarts. No sample tasks are added.

To use another file, set `TASK_MANAGER_DB_PATH` before starting the server. From
the repository root in PowerShell, substitute your own writable path:

```powershell
$env:TASK_MANAGER_DB_PATH = "C:\path\to\tasks.db"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

To return to the default on the next server start:

```powershell
Remove-Item Env:TASK_MANAGER_DB_PATH
```

Relative overrides resolve from the working directory; the default resolves from
the script directory. Databases, SQLite sidecars, environments, caches, logs,
coverage output, and common secret files are Git-ignored. This does not detect
secrets embedded in source files; review changes before committing.

## Upgrades and backups

Before the first launch of V2 against existing data, or a later schema upgrade:

1. Stop all app instances using the database.
2. Copy the configured database file to a safe backup location. The default is
   `data/tasks.db`; use your override path if configured.
3. Start the upgraded application. Initialization applies numbered migrations
   transactionally and preserves existing task IDs and content.

V1 did not record creation times. Migrated tasks therefore receive the upgrade
timestamp, not a recovered historical creation date. Newer schema versions and
unrecognized unversioned table layouts are rejected rather than guessed at or
overwritten. Migration mechanics are described in
[architecture](ARCHITECTURE.md#migrations).

There is no automatic downgrade. To roll back, stop all instances and restore the
pre-upgrade backup together with the prior application code. **Do not point V1 at
a V2 database**: V1 lacks revision checks and can bypass concurrency protection.

For a live backup, use SQLite's backup API. Copying an active database file is not
a reliable snapshot. Protect backups with the same access controls as task data.
Tests use isolated temporary databases and do not migrate the application database.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Database access error | Check that the configured path and parent directory are writable. Inspect the server terminal/logs for details. |
| Database is busy | Wait briefly and retry. Connections have a five-second lock timeout; failed writes are not blindly retried. |
| Newer or unknown schema | Use matching application code or restore a known compatible backup. Do not manually reset the schema version. |
| Edit conflict | Preserve any needed draft text, reload the latest task, and reapply your changes. |
| No matching tasks | Adjust search, category, or status filters. Global summary counts do not change with filters. |

Validation errors appear inline. Database exceptions are logged on the server and
shown generically in the browser. Closing the browser does not stop the server;
use Ctrl+C in its terminal.

## Limitations and security

The application supports local or small trusted-team use on one host. There is no
authentication, authorization, per-user ownership, encryption at rest, reminder
delivery, or audit history. Anyone able to reach the server shares the same tasks.
Bind to `127.0.0.1` for local use and protect OS/database permissions. Do not expose
the application publicly without an access-control and operational design.

SQLite serializes writers; sustained contention can exceed the five-second timeout.
Network-filesystem and multi-host database sharing are unsupported. Substring search
scans candidates, and deep OFFSET pages cost more. SQLite LIKE is ASCII
case-insensitive, not full Unicode case folding. Categories are single labels,
not many-to-many tags. Due dates use the server's date, not each browser's timezone.

See [deployment options](ARCHITECTURE.md#deployment-and-possible-expansion) for the
requirements and costs of authentication, PostgreSQL, REST clients, and containers.
