# Task Manager V2 architecture

[Project overview](../README.md) · [Usage and operations](USAGE.md) ·
[Development](DEVELOPMENT.md)

## Boundaries

Streamlit owns widgets, forms, session drafts and feedback. Services own runtime
validation and normalization. Persistence owns SQL and transactions. Shared models
contain data and the pure overdue predicate. Domain errors do not depend on the UI.
There is no ORM, SQL in the UI or task cache. A generic repository abstraction is
unnecessary for a single SQLite implementation.

| File | Responsibility |
| --- | --- |
| [`app.py`](../app.py) | Dashboard, forms, session drafts, and user feedback. |
| [`models.py`](../task_manager/models.py) | `Task`, `Priority`, `TaskPage`, `TaskSummary`, and the overdue predicate. |
| [`services.py`](../task_manager/services.py) | Input validation, normalization, and business operations. |
| [`database.py`](../task_manager/database.py) | Parameterized queries, connection lifetime, transactions, and pagination. |
| [`migrations.py`](../task_manager/migrations.py) | Numbered, additive schema changes. |
| [`errors.py`](../task_manager/errors.py) | `ConflictError` and `SchemaError`. |

## Service contracts

The functions below belong to `task_manager.services`. Every operation takes an
explicit file-backed `db_path` (`str` or `Path`). Call
`database.initialize_database(db_path)` before use. Imports do not create files or
connections. Each persistence operation opens a new connection, so separate
`:memory:` databases are unsuitable for this API.

### Task operations

| Function | Contract |
| --- | --- |
| `create_task(db_path, title, description="", priority=Priority.MEDIUM, completed=False, *, due_date=None, category="")` | Returns the persisted `Task`, including its assigned ID, revision, and UTC creation timestamp. |
| `get_task(db_path, task_id)` | Returns `Task` or `None` if missing. |
| `update_task(db_path, task)` | Replaces all editable fields using the supplied revision. Returns `True` if saved, `False` if missing; raises `ConflictError` if stale. Successful writes, including unchanged edits, increment the revision. Input is not mutated; reload before the next edit. |
| `set_task_completed(db_path, task_id, completed)` | Updates completion only. Returns `True` if found, `False` if missing. Repeating the current state succeeds without incrementing the revision. |
| `delete_task(db_path, task_id, *, expected_version=None)` | Returns `True` if deleted, `False` if missing or already deleted. A mismatched supplied revision raises `ConflictError`. The UI always supplies a revision; omission permits intentional administrative deletion by ID. |

Use `dataclasses.replace` to edit a retrieved `Task` while preserving fields you
are not changing. `created_at` is metadata, not an editable field. Revision checks
and the original UI snapshot are explained under [concurrency](#integrity-and-concurrency).

### Queries

| Function | Contract |
| --- | --- |
| `list_tasks(db_path, status="All", *, search="", category=None, sort="id")` | Returns an unbounded list for compatibility, export, or tests. The dashboard uses pages instead. |
| `get_task_page(db_path, status="All", *, search="", category=None, sort="id", page=1, page_size=10)` | Returns `TaskPage(tasks, total, page, page_size)`. Count and rows share one read snapshot; out-of-range pages clamp to the last available page. Empty results have page/pages equal to 1. |
| `get_summary(db_path, *, today=None)` | Returns global `TaskSummary(total, pending, completed, overdue)`. `today` defaults to the server's calendar date. |
| `list_categories(db_path)` | Returns distinct nonempty category labels. |

Status labels are exactly `All`, `Pending`, and `Completed`. A category of `None`
means all categories; `""` selects uncategorized tasks. Search is trimmed and
limited to 200 characters. Sort keys are `id`, `priority`, `due_date`,
`created_desc`, and `created_asc`; the API defaults to ascending ID order, while
the dashboard defaults to newest first. Pages must be positive integers, with
page sizes from 1 to 100. See [query behavior](#queries-and-performance).

### Validation and errors

| Input | Rule |
| --- | --- |
| Title | String, trimmed, nonempty, maximum 200 characters. |
| Description | String, whitespace preserved, maximum 10000 characters; empty allowed. |
| Priority | `Priority` member or exact `Low`, `Medium`, or `High` label; no case conversion or trimming. Defaults to Medium. |
| Completion | Actual boolean; integers and strings are rejected. Defaults to `False`. |
| Due date | `datetime.date` or `None`; strings and `datetime.datetime` are rejected. Past dates are allowed. |
| Category | String, trimmed, maximum 80 characters; case-sensitive, empty means uncategorized. |
| ID / revision | IDs must be integers, excluding booleans. Revisions must be positive integers, excluding booleans. Missing integer IDs follow the return contracts above. |

Duplicate titles are allowed. Invalid input raises `ValueError` before database
access, even for missing IDs. SQLite exceptions propagate to the UI boundary.
`SchemaError` reports incompatible schema versions/layouts. The persistence layer
enforces storage constraints; it does not trim titles or perform service validation.

## Integrity and concurrency

Edits carry the revision captured when the editor opened. Updates use one
`UPDATE ... WHERE id = ? AND version = ?`, incrementing the revision. If no row
matches, existence is checked in the same write transaction: False for a missing
ID, ConflictError for a newer revision. Models supplied by callers are not mutated.

Completion updates only completion/version, without reading and rewriting text,
dates or categories. Repeating the same state is idempotent. It deliberately uses
latest-state semantics rather than rejecting a stale detail snapshot.

The UI retains the original edit snapshot and draft across conflicts; reload is
explicit. Delete confirmation also carries a revision. Changed targets must be
reviewed and confirmed again. Administrative deletion without a revision remains
for compatibility, but the UI does not use it.

SQLite permits one writer at a time. Transactions are short, the timeout is five
seconds, foreign keys are enabled per connection, and connection contexts commit
or roll back and always close, including commit failures. The rollback journal is
retained; WAL is not necessary for this workload. Before adopting WAL, check the
bundled SQLite release/security fixes, filesystem constraints and backup strategy.
No network-filesystem or multi-host database sharing is supported. Failed writes
propagate to retry messages; non-idempotent operations are not blindly retried.

Concurrency tests use independent connections, barriers and explicit locks, not
sleeps. They verify stale-write rejection, simultaneous writers, preserved details
during completion, lock recovery, transaction rollback and connection closure.

## Migrations

`PRAGMA user_version` identifies numbered additive migrations. An immediate write
transaction serializes initialization and rechecks the version under the lock.
DDL and version advancement commit together. Current schemas avoid startup write
locks. Newer versions and unknown unversioned table layouts fail closed.

1. Adopt/create the original tasks table.
2. Add positive task revisions.
3. Add due date, category and creation timestamp; create query indexes.

Original IDs and contents are preserved. Legacy creation timestamps were never
recorded, so migrated rows receive upgrade time. Only supported service/database
APIs are application write paths; manual raw SQL may bypass validation/metadata.

For upgrade, backup, and rollback procedures, see
[usage and operations](USAGE.md#upgrades-and-backups). Schema changes must preserve
existing data and advance the version only after the migration succeeds.

## Queries and performance

Status/category predicates, literal substring search, sorting and LIMIT/OFFSET
execute in SQLite. Count and page selection share a read snapshot. Pages clamp
after deletion and have a maximum size of 100. Metrics use one aggregate query.
Values are parameters; sort expressions come only from a fixed allowlist.

Indexes cover status/ID, category/status/ID, creation ordering, priority ranking
and pending due dates. They do not turn leading-wildcard searches into indexed
lookups. Unicode text round-trips, but LIKE is not full Unicode case folding.
ID tie-breakers make sorting deterministic; concurrent insertions can still shift
offset pages between interactions. FTS or keyset pagination needs measured scale
requirements before adding complexity.

## Quality and security

The [development guide](DEVELOPMENT.md) documents test isolation, coverage, Ruff,
CI permissions, and dependency updates. Annotations do not perform runtime
validation; service validation and storage constraints serve different purposes.

No secrets are required. Database exceptions are logged server-side and shown
generically to users. Titles/descriptions use text rendering, not unsafe HTML.
Services enforce field lengths, date/enum/boolean/ID/revision types; annotations
alone do not validate input. Legacy content is preserved rather than trimmed.

## Deployment and possible expansion

The supported starting point is a server bound to 127.0.0.1. A small trusted team
can share one protected host, with no per-user privacy. Public deployment requires
an explicit security and operational design.

| Option | Justifying requirement | Cost/change |
| --- | --- | --- |
| FastAPI/REST | Independent clients or integrations | API contracts, HTTP errors, auth, separate server lifecycle and tests |
| Auth/multi-user | Untrusted users or private tasks | Identity provider, ownership migration, authorization on every operation, privacy tests and account operations |
| PostgreSQL | Multiple hosts or sustained competing writes | Managed database, credentials, pooling, migrations, backup/restore and load tests |
| Docker | A target requiring consistent packaging | Image updates, non-root runtime, durable volume, health checks and scanning |
| Hosted Streamlit | A chosen host with durable writable storage | Verify restart persistence, access control, monitoring and backups; ephemeral local SQLite is insufficient |

These are possible extensions, not implemented features. The current application
uses Streamlit and local SQLite without extra infrastructure.
