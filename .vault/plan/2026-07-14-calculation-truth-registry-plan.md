---
tags:
  - '#plan'
  - '#calculation-truth-registry'
date: '2026-07-14'
modified: '2026-08-25'
body_hash: 'sha256:6bf3bef8eec08bb7859f3f7462afcb64174675b9fe026066e5cd42dfa9556974'
tier: L2
related:
  - '[[2026-07-12-calculation-truth-registry-plan]]'
  - '[[2026-07-14-calculation-truth-registry-audit]]'
  - '[[2026-07-14-calculation-export-import-adjudication-adr]]'
---

# `calculation-truth-registry` plan

### Phase `P01` - Modelo 131 2024 revision completion

Close the confirmed gap where the Modelo 131 2024 revision lacks the modulos-engine formula, parameter, and casilla fragments that the 2025 and 2026 revisions already carry.

- [x] `P01.S01` - Author the Modelo 131 2024 modulos-engine formula, parameter, and casilla fragments mirroring the 2025 and 2026 revisions; `src/cadrumo/_data/registry/aeat/modelos/131/revisions/2024/`.
- [x] `P01.S02` - Land the Modelo 131 2024 export-roundtrip, historical date-axis, and live-filed-data-parser behaviour tests the legacy plan's own sub-bullets still list open; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Modelo 100 Renta residual calculation build

Complete the Modelo 100 (Renta) capital gains/losses, base reductions, minimums and brackets, CCAA deductions, and final-settlement calculation chain that the legacy plan's own annotations show substantially unbuilt.

- [x] `P02.S03` - Build the Modelo 100 capital gains and losses calculation chain against BOE/AEAT worked examples; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [x] `P02.S04` - Build the Modelo 100 base reductions, minimums, and bracket calculation chain against BOE/AEAT worked examples; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [x] `P02.S05` - Build the CCAA deduction and final-settlement calculation chain closing Modelo 100's Wave 21 residual scope; `src/cadrumo/_data/registry/aeat/modelos/100/`.

## Description

This is the canonical registry implementation backlog authorized by
`2026-07-12-calculation-truth-registry-plan` `P02.S03`. It contains only the
rows the 705-row legacy-plan disposition ledger
(`2026-07-14-calculation-truth-registry-audit.md`) classified as genuinely
actionable after the full row-by-row classification closed: the Modelo 131
2024 revision's missing modulos-engine formula/parameter/casilla fragments and
its dependent behaviour tests, and the Modelo 100 (Renta) residual calculation
build (capital gains/losses, base reductions, minimums and brackets, CCAA
deductions, and final settlement) that the legacy plan's own interleaved
`[x]`/`[ ]` annotations show substantially unbuilt. It excludes every row the
ledger resolved as delivered, superseded, blocked-external, blocked-derivative,
or inherited from the completed `calculation-export-import-adjudication` plan
(190/193/347/369/840 export-layout candidates, all of which failed that
plan's four-condition implementation gate). It also excludes the ledger's ~15
explicitly named unverified rows, which are verification debt (a full-suite
run and a repo-wide static-discovery sweep), not new implementation scope.

Every Modelo 100 Step must derive its expected calculation values from BOE
articles, AEAT manuals, or AEAT worked examples per
`no-tautological-calculation-tests` and `aeat-calculation-grounding` — never
hand-computed from the same formula under test.

## Parallelization

`P01` (Modelo 131 2024) and `P02` (Modelo 100 Renta) touch disjoint modelo
registry trees and may run in parallel. Within `P02`, `P02.S03` (capital
gains/losses), `P02.S04` (base reductions/minimums/brackets), and `P02.S05`
(CCAA deductions/final settlement) form a dependency chain — the final
settlement in `P02.S05` folds in the bases `P02.S04` produces, which in turn
consumes casilla-level gains/losses from `P02.S03` — so `P02.S03` precedes
`P02.S04` precedes `P02.S05`. Within `P01`, `P01.S01` (author the missing
fragments) precedes `P01.S02` (tests against those fragments).

## Verification

The plan is complete when every Step is closed and: the Modelo 131 2024
revision's registry tree matches the 2025/2026 revisions' fragment-directory
shape (casillas, formulas, parameters all present); the Modelo 131
export-roundtrip, historical date-axis, and live-filed-data-parser tests pass
against real registry data; and the Modelo 100 capital gains/losses, base
reduction, minimums/brackets, CCAA deduction, and final-settlement casillas
compute correctly against real BOE/AEAT worked examples, not hand-derived
expectations. `uv run --no-sync pytest --collect-only -q` and the project's
registry-build validation gate must stay green throughout.
