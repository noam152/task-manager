# Task Manager V2 implementation record

This is the completed V2 plan and delivery record, retained for historical context.
For current behavior, see [architecture](ARCHITECTURE.md); for checks to run on
your checkout, see [development](DEVELOPMENT.md). Findings and results below
describe the V2 upgrade, not outstanding defects or live CI status.

The baseline was clean `main` at `4426ced`, with 103 passing tests on Python 3.12.10.

## Findings at the start of V2

- Completion read and then replaced a full row, risking lost edits.
- Full edits had no revision check; stale forms could overwrite newer changes.
- The editor reloaded the latest row during submission, hiding the age of its draft.
- Initialization could not evolve existing data; filtering loaded all records.
- Due dates, search, categories, pagination, summaries, and quality gates were missing.
- SQL parameters and connection cleanup were sound and were retained.

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
   and optional future technologies. License selection preceded adding MIT.

The upgrade used a dedicated branch with tests committed alongside each phase.
Its scope excluded testing against user data, pushing, merging, deploying, or
changing repository settings.

## Completion record

| Phase | Local verification |
| --- | --- |
| Baseline | 103 existing tests passed; clean main matched origin/main. |
| Integrity | 113 total tests passed, including migration and concurrency regressions. |
| Queries | 147 backend tests passed, including search escaping, sorting and page bounds. |
| Dashboard | 169 total tests passed; fixed a pagination trigger regression found by AppTest. |
| Delivery | 172 tests passed; 98.19% combined statement/branch coverage; Ruff lint/format and diff checks passed. |

At delivery, workflow YAML/TOML and CI gates were checked locally. A pip dry run
resolved pinned dependencies for Python 3.12 Linux wheels; it did not execute the
hosted Ubuntu workflow. These are historical results, not a current CI report.
Uncovered paths at delivery were defensive direct-database argument checks, a
schema version race guard, and minor UI presentation/import branches. No critical
write path was excluded from coverage measurement.

The delivery included an MIT license. No real user database was migrated during
implementation, and no remote push, merge, deployment, history rewrite, or
repository-settings change was performed as part of that work. Follow the current
[backup instructions](USAGE.md#upgrades-and-backups) before upgrading existing data.
