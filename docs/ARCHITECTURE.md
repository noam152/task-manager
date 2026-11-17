# Task Manager V2 architecture

## Boundaries

Streamlit owns widgets, forms, session drafts and feedback. Services own runtime
validation and normalization. Persistence owns SQL and transactions. Shared models
contain data and the pure overdue predicate. Domain errors do not depend on the UI.
There is no ORM, SQL in the UI or task cache. A generic repository abstraction is
unnecessary for a single SQLite implementation.

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

## Migrations and backups

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

Stop all instances and back up before upgrading. There is no automatic downgrade:
restore the prior backup with the prior code. A live backup must use SQLite's
backup API, not a file copy while writes are active. Protect backups as sensitive
task data. Tests never open the application database.

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

Ruff checks lint/import ordering and formatting. pytest-cov measures statements
and branches, including UI code, with a 90% combined gate. Uncovered paths are
reported rather than hidden with blanket exclusions. Versions/action SHAs are
pinned; hash verification and recurring dependency-advisory audits remain future
hardening, not claimed guarantees. Review dependency changes through CI.

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

None of these is added without those requirements. No infrastructure, deployment,
GitHub settings or remote history is changed by this upgrade.
