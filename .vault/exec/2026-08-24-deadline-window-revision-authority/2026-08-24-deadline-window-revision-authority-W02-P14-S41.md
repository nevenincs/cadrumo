---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f2de2e9ca21546848ef08073bb1b73ad37e88a0087eb04f032a6cac0cfe18ce8'
step_id: 'S41'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 131 deadlines for supported filing years 2022-2026 and materialise all 4 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/131/`

## Description

- Discover the existing revision, period, cadence, supported-year, authority-projection,
  filing-window, and source-applicability authorities with Vaultspec RAG.
- Confirm exact production symbols and the complete Modelo 131 revision corpus.
- Transcribe the four missing 2022 quarterly coordinates from bundled official AEAT
  taxpayer calendars without deriving dates.
- Close the revision and construct over the new deadline IDs and their official legal
  and source evidence.
- Preserve following-year calendar semantics through the existing deadline-window span
  authority when a construct aggregates its deadline member citations.
- Add biting census, date, source, construct, canonical-owner, authority-projection, and
  source-axis regression coverage.

## Outcome

Modelo 131 now declares exactly four unique quarterly coordinates for filing year 2022,
the exact measured gap. The first three quarters cite the 2022 calendar and the fourth
quarter cites the 2023 calendar in which it is physically presented. All four published
bank cutoffs are retained.

The source-applicability checker now excludes construct aggregation from its existing
non-deadline-source census. It continues to reuse `_deadline_window_source_spans` and
still refuses a source used by any genuine non-deadline record outside the revision.
This resolves the construct-closure conflict without a Modelo 131 exception or a second
source classifier.

Vaultspec RAG and exact-symbol confirmation found no selector, resolver, period parser,
cadence authority, supported-year horizon, deadline catalogue, date table, or downstream
deduplication introduced by this step. Focused Ruff passed, and 52 source-applicability,
Modelo 131 registry, and deadline-engine tests passed.

## Notes

The first focused run correctly exposed missing construct legal closure. The next run
exposed that construct-required following-year calendar refs were misclassified as
generic construct evidence. The canonical checker repair resolves that conflict while
keeping stale non-deadline source refusal intact. Seventeen integration-lane tests were
deselected by the repository's unit-lane marker policy. Unrelated concurrent worktree
changes were left untouched.
