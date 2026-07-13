---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S16'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---




# Fix the export filename schema in the test corpus to modelo-id-year-period with canonical period tokens

## Scope

- `src/cadrumo modelo export tests`

## Description

- Confirmed the canonical AEAT period tokens (`1T`/`2T`/`3T`/`4T`, `1P`/`2P`/`3P`/`4P`,
  `0A`, `01`-`12`) from `StandardPeriodCode` in `core/_period.py`.
- Swept the repo for the abbreviated `m<id>-` filename defect (missing the
  `modelo-` stem) and for the year/period-omitting variant of the schema,
  using `rg` for `m303-|m202-|m111-|modelo-303-` plus a targeted `tmp_path`
  literal sweep to find the full set.
- Fixed `test_export_headers.py:359` (`m202-2024-1p.boe` to
  `modelo-202-2024-1P.boe`) and `test_modelo_export_verb.py:486,521` (`m111-`
  and `m202-` to their `modelo-` equivalents).
- Fixed the three year/period-omitting sites in
  `test_e2e_ledger_m303_quarters_to_m390_annual.py` (lines 563, 689, 759):
  missing year on the first M303 quarter export, abbreviated `m303-` prefix
  on the per-quarter loop export, and missing period token `0A` on the M390
  annual export.
- Fixed `test_e2e_ledger_m130_quarters_to_m100_annual.py:724`
  (`m100-2024-export.xml` to `modelo-100-2024-0A.xml`, M100 being annual-only).
- Fixed `test_app_quickfile.py:360` (same missing-year defect as the M303
  e2e site), `test_modelo_202_modality_lifecycle.py:343`, and
  `test_modelo_202_required_binding_gate.py:198` (both refusal-path tests
  whose export never materialises, but whose `--output`/`output_path`
  literal still names the artefact; renamed to the filing_year/period
  actually in scope for each seed).
- Left the widespread pre-existing `modelo-<id>.txt` (no year/period)
  convention across `application/filing/tests/test_export.py` and siblings
  untouched -- a distinct, much larger convention orthogonal to this Step's
  named scope, and left the local-observation-spreadsheet import filenames
  (`m100-2024.csv`, `m130-2025q4.csv`) untouched -- those are operator input
  files, not export artefacts, so the export-filename schema does not apply.

## Outcome

10 filename literals across 7 test files aligned to
`modelo-<id>-<year>-<period>` with uppercase canonical period tokens.
Convention alignment only; no production code changed. Targeted suite run
(21 tests across all 7 touched files) passes; `ruff check` clean; scoped
`pytest --collect-only -q` over `application/modelo` and `entrypoints/cli`
collects cleanly (1249 collected, exit 0). Committed at `456a80468a`.

## Notes

No incidents. The scope decision to exclude the ~60-site `modelo-<id>.txt`
convention in `test_export.py` and the local-observation-spreadsheet import
filenames is a deliberate boundary, not an oversight -- both are separate,
pre-existing conventions outside the plan Step's named target files and the
`m<id>-`/year-period-omitting defect class this Step addresses.
