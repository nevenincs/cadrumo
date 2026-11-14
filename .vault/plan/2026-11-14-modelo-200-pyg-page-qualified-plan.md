---
tags:
  - '#plan'
  - '#modelo-200-pyg-page-qualified'
date: '2026-11-14'
tier: L1
related:
  - '[[2026-11-14-modelo-200-pyg-page-qualified-adr]]'
modified: '2026-11-14'
body_schema: body-v2
body_hash: 'sha256:47f575bb855205e12cb63cc17ab487798dfe2f36611308dac20582217e4affb1'
---

# `modelo-200-pyg-page-qualified` plan

Modelo 200's PyG lines become page-qualified casillas, and stored bare ids migrate to them.

## Description

Approved 2026-11-14. Basis: the operator approved the proposed ADRs at 13:54 on condition that they do not diverge from the delta-keyed, compacted registry, and PRIME accepted `2026-11-14-modelo-200-pyg-page-qualified-adr` on that authority with option (a) and ordered this L1 plan with the ADR's four Steps (RULINGS 13:54).

The work declares each Modelo 200 PyG line page-qualified once at its earliest identical edition, migrates stored calculation revisions, overrides, work inputs, observations and bindings from the bare ids, supplies the sociedad persona's PyG, and reruns its four rows. The accepted ADR governs every Step. Binding conditions from it: the 29 same-number declarations on `pyg-wip` (`9de3e98698`) are not landed as they stand, and every byte-for-byte restatement is dropped; `delta_minimality` and `edition_delta_assessment` are green; layouts are regenerated only where the design changed; the migration refuses ambiguous rows; no filing grade rises. The 2024 grade change on `m200-2024-grade` keeps its own review bar.

## Steps

- [x] `S01` - Declare each Modelo 200 PyG line page-qualified once at its earliest identical edition, rebased from pyg-wip with every byte-for-byte restatement dropped; `src/cadrumo/_data/registry/aeat/modelos/200`.
- [ ] `S02` - Migrate stored bare PyG ids to their page-qualified ids with a dry-run preview, a before and after equality test and an ambiguous-row refusal; `src/cadrumo/application/modelo`.
- [ ] `S03` - Supply the sociedad persona PyG work inputs and retire its not-sourced expectation blocks; `dev/personas`.
- [ ] `S04` - Rerun the four sociedad Modelo 200 rows through backend, CLI, TUI and window; `X:/code/cadrumo/.tmp/2026-11-11-prime/table`.

## Parallelization

The Steps run in order. S02 needs S01's ids, S03 needs both, and S04 measures the result. One worker, CALC-IVA, on `lane/iva`.

## Verification

- S01: `just check-registry` (with `delta_minimality` and `edition_delta_assessment` green), `just check-registry-gate` and `just check-bindings` pass. The edition-delta migration reports no restatement left. Only the editions whose design changed have regenerated layouts.
- S02: the dry-run preview lists every row it would rewrite. Every calculated casilla value is equal before and after on real stored revisions. An ambiguous row is refused by test.
- S03 and S04: the four sociedad M200 rows (2022 to 2025) are green in the backend persona table, and CLI, TUI and window agree.
- Every supported year is enumerated from the registry envelope, with no year literals. No filing grade changes.
- The plan closes when every Step is checked and the final review passes.
