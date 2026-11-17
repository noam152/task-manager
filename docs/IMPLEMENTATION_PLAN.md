# Task Manager V2 implementation plan

Baseline: clean `main` at `4426ced`; 103 tests pass on Python 3.12.10.

## Review findings

- Completion performs a read followed by a full-row update, risking lost edits.
- Full edits have no revision check; a stale form can overwrite another session.
- The editor reloads the latest row during submit, hiding the age of its draft.
- Initialization cannot evolve existing data; filtering loads all records.
- Missing due dates, search, categories, pagination, summaries and quality gates.
- SQLite parameters and connection cleanup are already sound; retain these layers.

## Phases and acceptance criteria

1. **Integrity:** transactional numbered migrations preserve V1 IDs and data;
   stale writes raise explicit conflicts; completion updates only its own field;
   rollback, independent-connection and simultaneous-writer tests pass.
2. **Queries:** due dates, categories and creation timestamps persist; search,
   filters, stable ordering and bounded pagination execute in SQLite; summary
   counts and validation have boundary and injection regression tests.
3. **Dashboard:** existing create/edit/complete/delete flows remain accessible;
   metrics, filters, due dates, categories and paging work; stale edit/delete
   actions explain conflicts and require reload/reconfirmation; AppTest covers them.
4. **Delivery:** lint, format, branch coverage and the full suite pass; CI enforces
   them; README and architecture notes explain migrations, backups, limitations
   and optional future technologies. Add MIT only after the user's selection.

Use a dedicated local branch and commits containing tests alongside each phase.
Never test against application data, push, merge, deploy or change GitHub settings.

## Completion record

| Phase | Local verification |
| --- | --- |
| Baseline | 103 existing tests passed; clean main matched origin/main. |
| Integrity | 113 total tests passed, including migration and concurrency regressions. |
| Queries | 147 backend tests passed, including search escaping, sorting and page bounds. |
| Dashboard | 169 total tests passed; fixed a pagination trigger regression found by AppTest. |
| Delivery | 172 tests passed; 98.19% combined statement/branch coverage; Ruff lint/format and diff checks passed. |

Workflow YAML/TOML and all required CI gates were checked locally. A pip dry run
resolved the pinned dependencies for Python 3.12 Linux wheels. Actual Ubuntu CI
execution awaits a separately authorized push/PR. The remaining uncovered paths
are defensive direct-database argument checks, a schema version race guard and
minor UI presentation/import branches. No critical write path is excluded.

The user selected MIT after being presented license choices. No real user database
was migrated during implementation. Back up before launching V2. No remote push,
merge, deployment, history rewrite or repository-settings change was performed.
