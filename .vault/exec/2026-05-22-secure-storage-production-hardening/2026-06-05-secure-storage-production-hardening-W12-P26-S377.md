---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S377'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S377 - Close AFR-275 for CLI common helpers

Scope: close `AFR-275` for `src/aeat/entrypoints/cli/_common.py` with signals
`active-profile, manifest-bucket, sql-route`, target `manifest-discovery`, and owner
`W12.P22.S90`.

## Description

- Audited `_common.py` for active-profile resolution, repository construction,
  storage-route discovery, direct SQL/file access, localized error handling, and CLI
  output rendering.
- Confirmed no deprecated `config init` surface or environment wrangling is introduced
  by the shared CLI helper.
- Confirmed no direct SQL engine, raw database URL, manifest parser, or secure-object
  adapter is constructed in `_common.py`; the helper consumes typed workflow,
  transaction, invoice, and filing repositories.
- Bound Renta aggregation invoice reads to the same resolved active bucket id used for
  the aggregation request so transaction and invoice input repositories cannot diverge
  by re-resolving active-profile state independently.
- Kept user-facing helper messages on existing `tr()` locale keys and verified the
  locale catalogue through the canonical `python -m aeat.locales` interface.
- Closed `W12.P26.S377` through `vaultspec-core vault plan step check` and updated the
  `AFR-275` register status to `closed`.

## Outcome

`AFR-275` is closed. `_common.py` remains a CLI transport and repository-access helper,
not a manifest-discovery or storage-runtime owner. Its active-profile refusal path is
localized, and its Renta aggregation path now carries a single bucket binding through
transaction and invoice source resolution.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_common.py src/aeat/entrypoints/cli/tests/test_common.py src/aeat/application/aggregation/tests/test_renta_ledger.py src/aeat/entrypoints/cli/tests/test_backend_boundary.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_common.py src/aeat/application/aggregation/tests/test_renta_ledger.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_backend_boundary.py -k "boundary_inventory_rows_have_live_source_anchors or manual_ledger_root_format_still_controls_emitted_payload_shape"`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_common.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The first backend-boundary pytest invocation selected zero tests because the project
default marker expression excludes integration tests. It was rerun with `-m integration`
and the selected tests passed.
