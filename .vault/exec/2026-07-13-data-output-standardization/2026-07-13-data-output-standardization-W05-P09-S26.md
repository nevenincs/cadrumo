---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S26'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Promote one canonical public isolation fixture covering every settings dir field, with a structural coverage gate

## Scope

- `src/cadrumo/tests/secure_sql.py`

## Description

- Read every existing `_isolated_cli_backend` autouse-fixture definition
  across the ~22 sites (`rg _isolated_cli_backend`) and the two existing
  docstrings (`test_active_profile_confirmation_golden.py`,
  `test_lifecycle_contradiction_golden.py`) that explain the duplication is
  a deliberate workaround for the cross-package private-import rule: the
  intra-package `entrypoints/cli/tests/_modelo_work_ux_support.py` already
  centralises the fixture for its own package, but `agent/eval/tests/` (a
  sibling package) cannot import it, so it re-declares the identical body.
- Confirmed, against `core/config.py`'s `_STATE_ROOT_DERIVED_DIRS` taxonomy
  (landed by `W01.P01.S01`/`S02`), that every generated-output directory
  field — including the five fields the `test_config.py` variant hand-lists
  (`cadrumo_token_dir`, `cadrumo_runs_dir`, `cadrumo_financial_txs_dir`,
  `cadrumo_invoices_dir`, `cadrumo_drafts_dir`) — now derives its default
  from `cadrumo_local_storage_root`, so isolating the root alone (via the
  existing `isolated_profile_storage_root` helper) is now sufficient; the
  explicit 5-field override block is redundant post-Wave-W01.
- Added a new public `isolated_cli_backend` pytest fixture to
  `src/cadrumo/tests/secure_sql.py` (already a cross-package-importable,
  `__all__`-exported module) reproducing the most common existing shape
  (`dispose_engine()` before/after, `cadrumo_output_language="en"`,
  `isolated_profile_storage_root(tmp_path=tmp_path)`) so every consumer can
  import it directly instead of re-declaring the override block — this is
  the promotion-before-rewrite fix the shared-index rule calls for: the
  duplication existed because the helper was not importable, not because
  the logic itself needed 22 independent authors.
- Authored a structural coverage-gate test,
  `src/cadrumo/core/tests/test_isolation_fixture_state_root_coverage.py`,
  that requests the fixture, then DYNAMICALLY enumerates every field name in
  `_STATE_ROOT_DERIVED_DIRS` (never a hardcoded field list) and asserts each
  resolves under the fixture's isolated `tmp_path` — so a future dir field
  added by a sibling wave (W01.P02's corpus-text cache, W02's retention
  fields) is covered automatically the moment it lands in `config.py`.

## Outcome

- `isolated_cli_backend` is exported via `secure_sql.py`'s `__all__`; a
  consumer imports it with
  `from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend`
  (the self-name-preserving alias, matching the intra-package precedent) to
  keep it recognised as an autouse fixture under the expected parameter
  name.
- The coverage-gate test asserts `settings.cadrumo_local_storage_root`
  equals the fixture's yielded root, then asserts every
  `_STATE_ROOT_DERIVED_DIRS` field resolves under the test's `tmp_path` (not
  narrowly under the yielded `aeat-storage` subdirectory — the fixture's
  underlying `isolated_profile_storage_root` deliberately keeps
  `cadrumo_secret_store_dir` as a sibling of the storage root, matching
  production custody, so the true isolation boundary is `tmp_path`).
- `uv run --no-sync pytest src/cadrumo/core/tests/test_isolation_fixture_state_root_coverage.py -m integration`
  passes (2/2); `uv run --no-sync pytest --collect-only -q` collects clean
  (12839 tests, 0 errors); `ruff check` / `ruff format --check` on both
  touched files pass clean.

## Notes

While spot-verifying an existing `isolated_profile_storage_root` consumer
(`src/cadrumo/entrypoints/cli/_config/tests/test_config.py`, untouched by
this Step — `git diff` on it is empty), 3 of its tests failed for a
pre-existing reason unrelated to this Step:
`_corrupt_bucket_db` looks for the bucket directory under
`tmp_path / "cadrumo-storage"`, but the real fixture creates
`tmp_path / "aeat-storage"` — a directory-name drift left over from the
naming-rename wave. Flagging for the S27/S28 sweep or a separate fix; not
addressed here since it is out of this Step's scope.
