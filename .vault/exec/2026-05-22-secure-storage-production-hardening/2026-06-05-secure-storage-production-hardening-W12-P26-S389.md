---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S389'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S389 - Close AFR-287 for root landing rendering

Scope: close `AFR-287` for `src/aeat/entrypoints/cli/_root_landing.py` with signal
`active-profile`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `_root_landing.py` as the renderer for the bare `aeat` invocation.
- Confirmed the module consumes an application-owned `RootLandingReport` and renders
  localized `tr()` lines only.
- Confirmed the module does not resolve active-profile state, inspect manifests, load
  settings, open storage repositories, or catch exceptions.
- Confirmed the active-profile signal is already projected upstream by the root callback
  through `build_root_landing_report(active)`.
- Updated the root-help cold-start assertion to match the current localized
  `--tax-id DNI/NIE/NIF/CIF` guidance.
- Closed `W12.P26.S389` through `vaultspec-core vault plan step check` and updated the
  `AFR-287` register status to `closed`.

## Outcome

`AFR-287` is closed as `manifest-discovery`. The root landing renderer remains a
presentation-only boundary; active-profile discovery stays outside this module.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_root_landing.py src/aeat/entrypoints/cli/tests/test_root_help_shape.py src/aeat/application/operator_surface/tests/test_contract.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_root_help_shape.py src/aeat/application/operator_surface/tests/test_contract.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

Initial validation exposed a shared-dirty Google config extraction error unrelated to
`_root_landing.py`. The broad extraction remains outside this S389 slice; the root
landing closeout only stages the localized guidance assertion and vault records.
