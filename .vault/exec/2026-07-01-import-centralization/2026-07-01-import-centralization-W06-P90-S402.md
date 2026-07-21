---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S402'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Extend the import-hygiene scanner to detect underscore-named __all__ entries and dispose the 8 pre-existing hits surfaced by honesty-review finding #7

## Scope

- `dev/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_scan.py`
- `src/aeat/tests/test_import_hygiene_gate.py`
- `src/aeat/application/live/__init__.py`
- `src/aeat/application/live/tests/test_filed_capture_calculation_history.py`
- `src/aeat/application/live/tests/test_iva_remote_state_acquisition.py`
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/entrypoints/cli/_config/tests/test_bucket_history_parsing.py`

## Description

- Added a Family-4 detector (`is_underscore_named`, `UnderscoreInAllViolation`,
  `find_underscore_in_all_violations`) to `dev/import_hygiene_scan.py`: flags
  any `__all__` entry whose name starts with `_` (dunders excluded), wired into
  the text report, the `MAGNITUDE` summary, and the `--json` payload.
- Added fixture-based unit tests for the detector plus a real-behavior gate
  against `discover_facades()` over the live tree to
  `dev/tests/test_import_hygiene_scan.py`.
- Ran the scanner and confirmed exactly 8 pre-existing hits: 7 in
  `aeat.application.live.__init__` (`_aggregate_iva_compensation_history_reports`,
  `_await_live_iva_surface`, `_filed_history_surface_timeout_ms`,
  `_latest_declarations_by_period`,
  `_persist_iva_compensation_history_observations_strict`,
  `_persist_latest_filed_calculation_observations`,
  `_suppress_live_iva_playwright_cancellation_noise`) and 1 in
  `aeat.entrypoints.cli._config.__init__` (`_parse_bucket_event_types`).
- Confirmed via `rg` that none of the 8 has a cross-package consumer; every
  reach is test-only and intra-package (the owning package's own `tests/`
  folder). Disposition for all 8: removed from `__all__` (the internals-that-
  leaked branch), not promoted to a public name.
- Discovered 3 of the 7 `aeat.application.live` symbols
  (`latest_declarations_by_period`,
  `persist_iva_compensation_history_observations_strict`,
  `persist_latest_filed_calculation_observations`) are defined with PUBLIC
  names in `_filed_observation_persistence.py`; the facade re-exported them
  under an invented private alias (`X as _X`). Rewrote the intra-package test
  to import them directly under their real public name from the owning
  submodule, closing that aliasing smell alongside the disposal.
- Rewrote the remaining 4 `_iva_remote_state` symbols and
  `_parse_bucket_event_types` test imports to reach the owning private
  submodule directly (legitimate: each test lives inside the owning package).
- Wired a hard-zero Family-4 gate
  (`test_family4_no_underscore_named_entries_in_any_facade_all`) into
  `src/aeat/tests/test_import_hygiene_gate.py` — no ratchet, no named-
  tolerance allowlist, since the disposal reached zero in this same Step.

## Outcome

- `dev/import_hygiene_scan.py` reports `FAMILY 4: underscore-named entries in
  __all__: 0 total` against the live tree.
- `pytest dev/tests/test_import_hygiene_scan.py` — 11/11 passed.
- `pytest src/aeat/tests/test_import_hygiene_gate.py` — 10/10 passed (was 9/9
  before this Step).
- `pytest src/aeat/application/live src/aeat/entrypoints/cli/_config -n auto`
  — 204/204 passed.
- `pytest --collect-only -q src/aeat` — 11731/14196 collected cleanly (2465
  deselected), no new collection errors.
- `ruff check --fix` and `ruff format` clean on every touched file.
- Landed as three commits: `350a42157c` (detector + fixture tests),
  `093ca48bb7` (disposal of the 8 + test import rewrites), `c479991638` (gate
  wiring + live-tree pin test), each with an explicit pathspec touching only
  the files listed above.

## Notes

- The Family-1 production (5) and test-only (54) baseline counts documented
  in the prior consolidated exec record
  (`.vault/exec/2026-07-02-import-centralization-exec.md`) are unchanged by
  this Step; Family 4 is an orthogonal axis (facade-declaration shape, not
  cross-package reach) and this Step's disposal touched only Family-4 sites.
- The plan's `vaultspec-core vault add exec --step` scaffold resolved against
  an unmatched pre-existing Step (`W01.P07.S07`, about PDF text extraction,
  unrelated to this work) when invoked without an explicit `--step`
  argument naming this remediation; that stray scaffold was deleted before
  it was ever staged. `W06.P90.S402` was added via `vault plan step add`
  (an additive, non-mutating-of-existing-state verb) to give this honesty-
  review remediation a genuine Step to scaffold against, consistent with
  `W06.P90.S400`'s mandate to track every honesty-review finding as a new
  Step. Per the harness mandate for this dispatch, `vault plan step check` /
  `vault feature index` / `vault check all` were not run; the Step's
  checkbox remains unchecked pending the coordinator's own closure pass.

### Closeout verification (2026-07-04)

Re-ran `dev/import_hygiene_scan.py` at HEAD: `FAMILY 4: underscore-named entries in __all__: 0 total`. The Family-4 detector (`find_underscore_in_all_violations`, landed in commit `350a42157c`) is present and wired into the text report, the `MAGNITUDE` summary, and the `--json` payload. The hard-zero gate `test_family4_no_underscore_named_entries_in_any_facade_all` in `src/aeat/tests/test_import_hygiene_gate.py` passes against the live tree. All 8 pre-existing hits stay disposed. This Step's acceptance criterion is met at HEAD; the checkbox is closed here.
