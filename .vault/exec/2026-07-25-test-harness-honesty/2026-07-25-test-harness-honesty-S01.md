---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S01'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
---

# CLOSED at commit ad2d2e3eda, the bare-.xls scan pattern carried a doubled backslash so it could never match a real literal and passed over four live sites, now corrected with three routed through the canonical constants, one documented Literal-alias escape guarded by a justification test, a positive control asserting every survivor pattern matches its target and rejects near-misses, and a non-empty-corpus assertion, verified by reintroducing a bare literal and observing the gate name the exact file and line

## Scope

- `src/cadrumo/tests/test_enum_constant_extraction_inventory.py`

## Description

- Measure the shipped pattern against the real production file set before editing: 1380 files, 0 hits.
- Measure the corrected pattern against the same set: 4 hits across 3 files.
- Correct `_RE_XLS_BARE` from `r'"\\.xls"'` to `r'"\.xls"'`.
- Route `_schema_references.py` record-design suffixes through `PDF_EXTENSION`, `XLS_EXTENSION`, `XLSX_EXTENSION`, `XLSM_EXTENSION`.
- Route `_ledger_import_cli.py` import-directory extensions through `XLS_EXTENSION`, `XLSX_EXTENSION`.
- Grant `_workbook_parity_models.py` a documented escape for its `Literal[...]` alias and the assertion pinning it to the constant.
- Add `test_xls_escape_still_needs_its_escape`, failing when the construct justifying the escape disappears.
- Add `test_bare_literal_patterns_discriminate`, asserting each survivor pattern against a must-match and a must-not-match input.
- Add `test_literal_survivor_scan_reads_a_non_empty_corpus`.

## Outcome

Closed at commit `ad2d2e3eda`.

The gate had passed since it was written while measuring nothing. In the raw
string `r'"\\.xls"'` the doubled backslash makes the pattern require a literal
backslash followed by any character before `xls`, which no real `".xls"` literal
contains. Measured, not inferred: over the 1380 production files the gate
selects, the shipped pattern returned 0 hits and the corrected pattern returns 4.

Three sites route through the canonical constants. The fourth is a `Literal[...]`
type alias; `Literal` accepts only literal forms and never a
`Final[Literal[...]]` constant, so that site cannot route through `XLS_EXTENSION`
and keeps a documented escape rather than a forced migration.

Discrimination proven rather than asserted: reintroducing a bare `.xls` literal
made the gate fail naming `_ledger_import_cli.py:164`, and the literal was then
restored.

Gates: 8 passed on the gate module, 3027 passed across the registry suite, 8
passed on the CLI import tests, ruff clean on all three changed files,
`pytest --collect-only -q` clean at 14081 collected immediately before the
commit. Staged set verified as exactly the three authored files.

## Notes

The audit reported three uncaught sites; the measured count is four, because the
workbook-parity module carries two occurrences on separate lines. The audit
itself flagged this discrepancy and it is recorded here rather than smoothed
over.

Semantic search was degraded throughout — the code index held roughly 1027
sections against roughly 4546 files while reporting an empty degraded-reasons
list. Discovery for this step was by direct reads, `rg`, and a measurement
script run against the real file set, never by semantic search. Tracked as S02
and S03 of this plan.

This step was executed by the coordinator rather than a dispatched agent: the
finding's owning agent hit a session limit before it could act, and the whole
fleet became unavailable shortly after.
