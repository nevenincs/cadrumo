---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Extend the modelo-export-mirrors-official-structure rule source to bind the fichero-BOE transport and mandate full-structure mirror-or-panic, then run vaultspec-core sync

## Scope

- `.vaultspec/rules/rules/modelo-export-mirrors-official-structure.md`

## Description

- Extend the `modelo-export-mirrors-official-structure` rule source to bind the fixed-width fichero-BOE transport: a pre-write hard panic on a structurally-thin `.boe`, keyed on value presence (not casilla-id membership, since `build_draft` emits EMPTY rows), scoped to `fixed_width`. Add Good/Bad examples and cite the review-found EMPTY-membership bug and its fix in the Source.
- Run `vaultspec-core sync` to propagate to all four provider copies plus the aggregated `CLAUDE.md`/`AGENTS.md`.

## Outcome

Committed in `25ae394ab` (7 files). Codified only after the gate completed a full implement -> review -> fix -> validate cycle, per the vaultspec-codify discipline (a lesson qualifies after it has held across one execution cycle; here the cycle included the code review that caught the critical EMPTY-membership defect).

## Notes

Edited the `.vaultspec/rules/` source and propagated via sync per aeat-vaultspec-centralisation; the generated provider copies were not hand-edited.
