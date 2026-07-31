---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:5d67d47627900fc3eb5caecda83b16f0b01fa60044da0f38afeb1c716e0f835a'
step_id: 'S28'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Sweep the isolated-storage fixture family and unify the two collection-time pytest storage roots into one cleanup-registered helper

## Scope

- `conftest storage roots`

## Description

- Read every `_isolated_storage` definition (`rg _isolated_storage`, 9 real
  fixture sites plus one false-positive test-name substring match in
  `test_root_help_shape.py`) and classified them into two shapes: 5
  non-CLI "Shape A" sites (`override_settings(cadrumo_local_storage_root=
  tmp_path[, cadrumo_active_profile=None])` + `dispose_engine` before/after,
  root set FLAT at `tmp_path` — no `aeat-storage` subdirectory nesting) and
  4 CLI "Shape B" sites (`with isolated_profile_storage_root(tmp_path=
  tmp_path): yield`, identical in shape to the minimal `_isolated_cli_backend`
  variant already centralised in `W05.P09.S27`).
- Discovered one of the 5 Shape-A sites
  (`adapters/persistence/storage/tests/_runtime_attached_repositories_support.py`)
  was genuinely DEAD: the file is a non-`test_`-prefixed shared-support
  module (never collected by pytest directly), and its
  `_isolated_storage` fixture was never imported by the one file that DOES
  import other symbols from it
  (`test_runtime_attached_repositories_part1.py`). Deleted the orphaned
  fixture outright rather than sweeping it onto a canonical import, per
  `no-dormant-source-resolvers`.
- Added a new canonical fixture, `isolated_storage_root`, to
  `src/cadrumo/tests/secure_sql.py` (a genuine `@pytest.fixture(autouse=True)`,
  matching `isolated_cli_backend`'s pattern rather than the plain-context
  -manager convention the module's OLDER helpers use) for the remaining 4
  live Shape-A sites: it points `cadrumo_local_storage_root` directly at
  `tmp_path` (NOT nested under `tmp_path / "aeat-storage"` like the existing
  `isolated_sessionless_storage_root`), because several Shape-A sites also
  write ancillary fixture bytes directly under the same `tmp_path` and the
  two paths must stay coincident. Swept the 4 live Shape-A sites
  (`application/filing/tests/test_runtime_repository.py`,
  `application/filing/tests/test_review_runtime_storage.py`,
  `adapters/persistence/profile/tests/test_modelo_runtime.py`,
  `adapters/persistence/profile/tests/test_filing_runtime.py`) onto it.
- Swept the 4 live Shape-B (CLI) sites onto the `W05.P09.S27` canonical
  `isolated_cli_backend` fixture, matching that Step's established pattern
  exactly.
- Unified the two independently-computed collection-time
  `<gettempdir()>/cadrumo-pytest-<pid>` storage roots (repo-root
  `conftest.py` and `src/cadrumo/conftest.py`) into one new shared module,
  `src/cadrumo/tests/_collection_storage_root.py` (pure-stdlib, zero
  Cadrumo-package imports, safe to import at the earliest point in
  collection): `collection_storage_root()` for the pure derivation,
  `register_collection_storage_root_cleanup(root)` for the `atexit`-based
  removal of `root` plus a best-effort sweep of any `cadrumo-pytest-*`
  sibling directory older than 24 hours, and `apply_collection_storage_root
  (*, overwrite=False)` combining both in one call.
- Hit and resolved a ruff `E402` quirk while wiring the repo-root
  `conftest.py`: ruff tolerates a bare `os.environ.setdefault(...)`
  expression-statement (any number of them) ahead of subsequent imports, but
  NOT a bound assignment or an arbitrary function-call statement — verified
  empirically with scratch probes. Restructured the repo-root conftest to
  keep only the literal `os.environ.setdefault(...)` call before the
  `import pytest` block, moving `register_collection_storage_root_cleanup(...)`
  to run AFTER the import block (harmless, since cleanup registration has no
  Settings-resolution-ordering constraint — only the env-var-set does).
- Verified the cleanup mechanism directly (not just via a full pytest run,
  since `-n auto` xdist workers can be hard-terminated, bypassing `atexit`
  for their own PID's directory): manually invoked
  `register_collection_storage_root_cleanup` against a live root plus a
  synthetic aged sibling directory, then ran `atexit._run_exitfuncs()` and
  confirmed both were removed.
- Two follow-ups requested by the team lead after the initial commit,
  folded into this Step rather than deferred:
  1. `src/cadrumo/tests/test_import_hygiene_gate.py` flagged
     `src/cadrumo/conftest.py`'s new reach into the private
     `cadrumo.tests._collection_storage_root` submodule as an
     undocumented test-only cross-package private import. Rather than
     adding another named entry to `dev/import_hygiene_test_debt.json`,
     promoted `collection_storage_root`, `register_collection_storage_root_cleanup`,
     and `apply_collection_storage_root` to the public
     `cadrumo.tests.__all__` facade (the module's own docstring already
     states it exists specifically to be shared by both conftests, so it
     is a genuine promotion candidate, not a one-off private reach) and
     retargeted both conftest imports at the public path.
  2. The `aeat-storage` directory-name literal inside
     `isolated_profile_storage_root` / `isolated_sessionless_storage_root`
     / `isolated_runtime_profile` / `isolated_two_bucket_runtime` (all in
     `secure_sql.py`) is an app-owned artifact name the naming-rename wave
     (ruling R4) missed. Renamed all 5 occurrences to `cadrumo-storage` and
     swept every literal consumer
     (`rg 'aeat-storage' src` after the rename returns nothing): the
     4 test files asserting on the on-disk path
     (`adapters/outbound/llm/tests/test_cache.py`,
     `adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`,
     `application/workflow/tests/test_persistence.py`,
     `domain/tests/test_runtime_repository_enrollment.py`), plus this
     Step's own `isolated_storage_root` docstring in
     `core/tests/test_isolation_fixture_state_root_coverage.py`. Confirmed
     the 3 previously-flagged `entrypoints/cli/_config/tests/test_config.py`
     failures (whose `_corrupt_bucket_db` helper already expected
     `cadrumo-storage`) now pass.

## Outcome

- `uv run --no-sync ruff check` / `ruff format --check` pass clean on all 12
  originally-touched files, plus the 2 conftest re-targeted imports,
  `tests/__init__.py`, and the 6 files touched by the `aeat-storage` rename.
- `uv run --no-sync pytest --collect-only -q` collects clean (12890 tests,
  0 errors).
- `src/cadrumo/tests/test_import_hygiene_gate.py` passes clean (11/11) —
  the private-submodule reach is gone.
- Ran the full test suite for all 8 live swept files plus the dependent
  `test_runtime_attached_repositories_part1.py`: 29/29 pass with
  `-m integration`, 61/61 pass with `-m "unit or integration"` — matching
  the pre-sweep baseline exactly (also 29 with `-m integration` before any
  edit).
- `entrypoints/cli/_config/tests/test_config.py`: 11/11 pass with
  `-m integration` (previously 8/11, 3 failing on the `aeat-storage` vs
  `cadrumo-storage` mismatch). The 5 `aeat-storage`-consumer files plus this
  file: 55/55 pass with `-m "unit or integration"`.
- Ran `src/cadrumo/core/tests/` and
  `src/cadrumo/domain/calculations/registry/tests/` as a broader sanity
  check on the conftest change (the highest-risk edit in this Step, since it
  touches collection-time behaviour for the whole suite): 357/358 and
  785/786 pass respectively, with exactly one unrelated pre-existing failure
  in each (an in-progress M210 IRNR registry-coverage gap and an in-progress
  docs-cli-sequences period-string gate finding — both confirmed via
  `git log`/`git diff` to be untouched by this Step and attributable to
  concurrent peer campaigns landing mid-implementation).

## Notes

None.
