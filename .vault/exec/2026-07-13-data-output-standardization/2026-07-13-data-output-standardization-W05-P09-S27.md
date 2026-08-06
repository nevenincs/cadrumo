---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:6df658485ce95ed4180283c2572ca633b90087e3adb18e746ecc63edf18decf3'
step_id: 'S27'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Sweep the copy-pasted isolated-cli-backend fixture copies onto the canonical fixture

## Scope

- `cli test isolation fixtures`

## Description

- `git diff` every one of the 22 sites carrying a local `_isolated_cli_backend`
  definition (plus the 6 sites that already import it from the intra-package
  `_modelo_work_ux_support.py` helper) before touching anything; all 22 were
  clean (no peer WIP).
- Swept the intra-package shared helper
  (`entrypoints/cli/tests/_modelo_work_ux_support.py`) onto the canonical
  import first, since 6 other files (`test_overview_prepare_verb.py`,
  `test_overview_pipeline_verb.py`, `test_overview_historical_work_units.py`,
  `test_modelo_revision_trace.py`, `test_modelo_work_readiness_ux.py`,
  `test_modelo_work_ux.py`) import its `_isolated_cli_backend` and needed no
  changes of their own once it delegated.
- Swept the remaining 21 standalone definitions onto
  `from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend`,
  grouped by shape:
  - 9 sites matching the canonical shape exactly (`dispose_engine()` +
    `override_settings(cadrumo_output_language="en")` +
    `isolated_profile_storage_root`): straight swap.
  - 4 sites carrying the now-redundant 5-field `override_settings` block
    (`cadrumo_token_dir`/`runs_dir`/`financial_txs_dir`/`invoices_dir`/`drafts_dir`)
    that `W01.P01` made derivable from the root alone: dropped the explicit
    overrides entirely.
  - 6 minimal sites (`with isolated_profile_storage_root(tmp_path=tmp_path):
    yield`, no output-language override, some without `dispose_engine()`):
    swapped after confirming empirically (baseline pass, then swapped pass)
    that none of their assertions are locale-sensitive to the canonical
    fixture's `cadrumo_output_language="en"` pin — the apparent positive
    English-text assertions in `test_modelo_discovery_defects.py` turned out
    to be internal/technical tokens (casilla ids, TSV field names, modelo
    codes), not localized operator prose.
  - `test_cli_workflow_verification.py` left untouched: its fixture overrides
    auth/certificate settings, a genuinely distinct concern from storage-root
    isolation, not a copy of the pattern this Step targets.
- Discovered and fixed a real pre-existing type-annotation bug along the way:
  several sites explicitly requested the fixture as `_isolated_cli_backend:
  Path`/`_isolated_cli_backend: None` even though the OLD per-site fixture
  bodies yielded `None` (a mismatched annotation); the canonical fixture
  genuinely yields the storage-root `Path`, so those annotations are now
  correct rather than misleading.
- Added `# noqa: F401 - autouse fixture` on the renamed import (ruff cannot
  see the implicit autouse binding) and `# noqa: F811` on individual explicit
  fixture-parameter requests where ruff's redefinition check fires against a
  same-named import — both are known, expected false positives for this
  established pytest-fixture-import pattern (the intra-package precedent this
  Step generalises already carries the same `noqa` shape).

## Outcome

- `uv run --no-sync ruff check` / `ruff format --check` pass clean on all 21
  touched files.
- `uv run --no-sync pytest --collect-only -q` collects clean, 0 errors.
- Ran the full test suite for every one of the 21 touched files plus the 6
  files that depend on the swept intra-package helper (28 files, 192 tests):
  192 passed, 3 failed — the same 3 pre-existing, unrelated failures recorded
  in `W05.P09.S26`'s exec record (`entrypoints/cli/_config/tests/test_config.py`'s
  `_corrupt_bucket_db` looking for `tmp_path/"cadrumo-storage"` while the real
  fixture creates `tmp_path/"aeat-storage"`). No new failures; no behaviour
  regression from the swap.

## Notes

The `entrypoints/cli/_config/tests/test_config.py` naming-drift bug remains
open and out of this Step's scope (unrelated to isolation-fixture
consolidation); flagged again here for whichever agent owns the naming-rename
follow-up.
