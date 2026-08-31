---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d669b377aae49d65cbfe4f0ab0a208c60f350fe4db7ab85021ef1220054c3d69'
step_id: 'S121'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---


# Refactor the size-budget subjects in declarations.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`

## Changes


- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`
- `A` `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/_declarations_support.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py`
- `M` `src/cadrumo/application/live/filed_data_capture.py`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part1.py::test_authoritative_declaration_selection_uses_latest_alta_row_for_duplicate_period src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py::test_capture_filed_declaration_empty_nif_carries_translated_message` -> `pass`
- `verify:` `uv run --no-sync python -c <canonical consumer capture-import assertion>` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.size_budget` -> `fail`

## Notes

The S121 implementation landed in verified predecessor `5c43de30cf` with other in-flight work; this record attributes the S121 paths and subsequent scoped validation without duplicating or reverting that commit.

Existing browser-backed Sede register fixtures cannot honestly exercise `capture_previous_filing_observations` or `capture_relation_source_observations`: their router supplies navigation/search HTML only and returns 204 for non-navigation traffic, with no Cotejo popup/PDF or submitted-file download protocol. No fabricated router or production injection seam was added.

The canonical size gate reports 93 remaining over-budget subjects owned by still-open P05 rows; `declarations.py` is absent from that list and measures 1,058 lines. No baseline was changed.
