---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S258]]'
---

# `secure-storage-production-hardening` `W12.P26.S258` Review

## S258-001 | HIGH | Recalculation delay was captured from Settings at import time

The parity harness resolved `Settings().aeat_calc_sheets_recalc_delay_s` into a module constant during import. That bypassed the centralized `load_settings()` override path used by tests and runtime settings scoping. The harness now resolves the delay at call time through `load_settings()`.

## S258-002 | MEDIUM | Unknown scenario casilla numbers were rendered in the exception string

`_build_operator_inputs` interpolated unknown scenario casilla numbers into the `CalcSheetsParityError` message. Scenario files can be externally supplied test artefacts, so the primary error now uses a stable message, a translated-message key, and count/modelo context without rendering the raw values.

## S258-003 | MEDIUM | Missing seed anchors were silently skipped

`_seed_inputs_into_sheet` skipped scenario inputs when a casilla, binding, or enum binding had no writable seed cell. That could produce a remote parity run that looked valid but omitted caller-supplied input. The harness now raises `CalcSheetsParityError` with `seed_anchor_missing` instead.

## S258-004 | PASS | Remote-mirror boundary is retained

The harness remains the remote parity driver: it builds a plan, applies it through the outbound Google adapter, writes scenario values, waits for recalculation, and reads formula values. No local persistence, credential serialization, logging, or environment reads were added.

## S258-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_parity_harness.py src/aeat/application/storage/calc_sheets/test_parity_harness_hardening.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_parity_harness_hardening.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py` passed with 24 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-156` as `remote-mirror` with settings resolution, scenario errors, and seed-anchor failure paths hardened.
