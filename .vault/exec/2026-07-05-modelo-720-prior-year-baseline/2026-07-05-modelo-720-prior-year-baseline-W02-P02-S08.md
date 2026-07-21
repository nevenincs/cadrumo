---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S08'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Author the M720 class-code taxonomy ADR covering B real estate, I IIC, V securities, S insurance, and the Modelo 721 virtual-currency split

## Scope

- `.vault/adr/`

## Description

- Grounded the step with semantic vault and code searches for Modelo 720 class-code taxonomy, row projection, IIC, real estate, and virtual-currency split.
- Confirmed the live code still maps `REAL_ESTATE` to `I` and exposes `VIRTUAL_CURRENCY` as a Modelo 720 class-code candidate.
- Confirmed the bundled AEAT Modelo 720 record design defines position 102 as `C`, `V`, `I`, `S`, and `B`, with `I` for IIC participations and `B` for real estate.
- Cross-checked the accepted Modelo 721 ADR/research: virtual currencies belong to the RD 1065/2007 art. 42 quater / Modelo 721 sibling path, not to Modelo 720 position 102.
- Authored `2026-07-05-modelo-720-prior-year-baseline-adr.md` as a proposed taxonomy ADR.

## Outcome

- The ADR chooses a closed Modelo 720 typed class-code contract: account `C`, security `V`, a new distinct IIC class `I`, insurance `S`, and real estate `B`.
- The ADR requires Modelo 720 projection to fail closed for virtual currency rather than emitting a sibling-model code.
- The decision preserves the existing `foreign_asset` row source and introduces no new binding source kind, resolver convention, or validator convention.

## Notes

- No source migration was performed in this step; that belongs to W02.P03.S09-S11.
- The plan and W01 exec records were already present as untracked worktree state before this step; this step only adds the ADR and S08 exec record, then checks S08 through the vault CLI.
