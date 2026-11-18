# Development and quality checks

[Quick start](../README.md#quick-start) · [Architecture and API](ARCHITECTURE.md) ·
[Usage and operations](USAGE.md)

## Environment and dependencies

Use Python 3.12. The quick start uses the environment's Python directly, so shell
activation and PowerShell execution-policy changes are unnecessary.

| File | Purpose |
| --- | --- |
| [`requirements.txt`](../requirements.txt) | Pinned direct runtime dependency: Streamlit. SQLite support comes from Python. |
| [`requirements-dev.txt`](../requirements-dev.txt) | Includes runtime requirements plus pytest, pytest-cov, and Ruff. |
| [`requirements-dev.lock`](../requirements-dev.lock) | Version-pinned runtime and development dependency snapshot, including transitive packages. Used by quick start and CI. |

The lock is not a package-hash integrity lock or a vulnerability-audit guarantee.
Package hashes and recurring dependency-advisory checks are potential hardening
work; they are not part of the current quality gates.

## Local checks

Run from the repository root after installing the locked environment. PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing --cov-report=xml
git diff --check
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
Ruff's configuration and coverage settings are in [`pyproject.toml`](../pyproject.toml).
[`pytest.ini`](../pytest.ini) sets `tests/` as the discovery directory and adds the
repository root to pytest's import path.

### Focused tests

Append a test file to the pytest command. For example:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_integrity.py
.\.venv\Scripts\python.exe -m pytest tests/test_app.py
```

| Test file | Coverage area |
| --- | --- |
| [`test_database.py`](../tests/test_database.py) | CRUD, defaults, missing IDs, persistence, rollback, and connection cleanup. |
| [`test_integrity.py`](../tests/test_integrity.py) | Migration compatibility/rollback, stale writes, simultaneous writers, initialization, locks, and version-checked deletion. |
| [`test_queries.py`](../tests/test_queries.py) | Due dates, validation boundaries, literal search, sorting, pagination, counts, and indexes. |
| [`test_services.py`](../tests/test_services.py) | Business validation, normalization, task operations, filtering, and error propagation. |
| [`test_app.py`](../tests/test_app.py) | Streamlit AppTest flows, form resets, conflicts, pagination, and user feedback. |

Database integration tests use pytest's temporary paths. AppTest sets
`TASK_MANAGER_DB_PATH` to a temporary file before running the app. Validation unit
tests mock persistence calls. Tests never open the normal application database.
Concurrency regressions use barriers, independent connections, and explicit locks
rather than timing-dependent sleeps. AppTest is included with Streamlit.

### Coverage

Coverage includes `task_manager` and `app.py`, with branch measurement and a **90%
combined statement/branch floor**. The terminal report identifies uncovered paths;
they are not hidden with blanket exclusions. XML output is written to ignored
`coverage.xml`. For an optional HTML report:

```powershell
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=html
```

Open `htmlcov/index.html` after generation. Coverage output and tool caches are
Git-ignored. Historical V2 results are in the
[implementation record](IMPLEMENTATION_PLAN.md#completion-record), not a guarantee
of the current checkout's results.

## GitHub Actions

[`tests.yml`](../.github/workflows/tests.yml) runs on pushes to `main` and pull
requests targeting `main`. One Ubuntu job uses Python 3.12, installs
`requirements-dev.lock`, runs Ruff lint/format checks, and executes:

```sh
python -m pytest --cov --cov-report=term-missing --cov-report=xml
```

The workflow uses read-only repository permissions, disables persisted checkout
credentials, and has a ten-minute timeout. Actions are pinned to commit SHAs;
update each SHA and its release comment together. It requires no project secrets
and has no deployment or repository-write steps. Check GitHub's run results to
confirm Ubuntu execution; local checks alone do not verify the hosted workflow.

## Dependency updates

Use a **clean Python 3.12 environment** so unrelated packages do not enter the lock:

1. Update the intended direct pins in `requirements.txt` or `requirements-dev.txt`.
2. Install `requirements-dev.txt` in that clean environment.
3. Run the full local checks, then generate a candidate snapshot with
   `python -m pip freeze` using that environment's Python.
4. Replace `requirements-dev.lock` with the reviewed pins, retaining its explanatory
   header. Review transitive changes as well as direct changes.
5. Recheck the locked installation and all quality gates, including Ubuntu CI,
   before adopting the update. Preserve required platform-specific dependencies.

Keep tests alongside functional changes in reviewable commits. Review staged diffs
for generated files and secrets; ignore patterns cannot inspect source contents.
