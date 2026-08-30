---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:aaa3a6535e9c642bf234919144816b2867d8425a6d7f0e3cb6995b2f637991e4'
step_id: 'S119'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Reconcile the export-layout join-ratchet inventory after the M184 literal publication, retaining only genuinely unjoined sheets and proving the newly joined M184 layouts

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py::test_the_scan_reaches_the_real_registry src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py::test_the_unjoined_design_sheet_inventory_is_exact src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py::test_every_inventory_entry_sits_on_a_multi_record_layout src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py::test_no_inventory_entry_is_an_auxiliary_envelope_header` -> `pass`

## Notes

- The four M184 entries were stale after the verified S64 literal-publication predecessors; this step changes only the ratchet inventory, not generated registry data or the runtime discriminator mechanism.
- The focused authority scan proves M184 has no remaining unjoined sheet and retains only M296's 2024-y-siguientes perceptor sheet. Its optional candidate span remains S69's runtime-identity decision and was not changed.
