---
tags:
  - '#exec'
  - '#eoy-final-calculation'
date: '2026-06-23'
modified: '2026-06-23'
step_id: 'S01'
related:
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---




# Ground the LIS deduccion/bonificacion casilla set that reduces cuota integra (00562) to cuota liquida (00592) against the AEAT Modelo 200 Diseno de Registros / Manual practico

## Scope

- `src/aeat/_data/registry/aeat/modelos/200`

## Description

- Read the bundled authoritative AEAT corpus `corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf.extracted.md` (Manual práctico de Sociedades 2024, pages 406-407) for the cuota-íntegra to cuota-líquida composition.
- Confirmed the registry chain: cuota íntegra `00562` is computed; cuota íntegra ajustada `00582` and cuota líquida `00592` are both `input_kind = "manual"` (the F2 defect), so they silently resolve to 0 and the downstream cuota a ingresar `00599` reads 0.
- Transcribed the exact, manual-grounded subtraction composition for both intermediate casillas (verbatim from the manual, not invented).

## Outcome

The cuota-líquida derivation is now authoritatively grounded for S02 implementation (bundled-corpus source, per `legal-grounding-verifies-bundled-authoritative-corpus`):

- `[00582]` cuota íntegra ajustada positiva = `([00562] + [01038]) - ([00567] + [00568] + [00563] + [00815] + [00566] + [00576] + [00569] + [00570] + [01344] + [01280] + [00572] + [00571] + [00573] + [00575] + [00577] + [00581])`; if the result is negative or zero, set both `00582` and `00592` to 0.
- `[00592]` cuota líquida = `[00582] - ([00583] + [00585] + [00584] + [00588] + [01039] + [02314] + [02315] + [00565] + [00590] + [00399] + [00082] + [01040] + [01041])`; the result is always positive or zero (floor 0). A cuota líquida mínima floor `00619` applies to affected entities.

Every subtrahend is an operator-entered deducción/bonificación casilla that defaults to 0, so for a no-deduction filer `00592 = 00562` (the common case the F2 audit reproduced: 80000 base, 18400 cuota íntegra, currently 00592/00599 = 0). The source is page 406-407 of the bundled Manual de Sociedades 2024; legal basis LIS arts. 29/30/31/32/33/39 (already on the casillas' `legal_refs`).

## Notes

- S02 (convert `00582` and `00592` from `input_kind = "manual"` to computed casillas carrying these two formulas, wire the owning construct + legal_refs, satisfy the construct-coverage validator) is a regulated registry change spanning ~30 casilla references across two formulas. It is now de-risked to a mechanical, grounded transcription, but each casilla id needs its `segmento` prefix resolved and the registry build + construct-coverage validator + tautology gate must stay green. Per the regulated-grounding and safety rules it should be implemented carefully (dedicated executor or owner go-ahead) and is coordinated with the peer-active M200 area (tasks #5/#13/#14). A no-deduction end-to-end check (80000 base -> 00592 = 18400 -> 00599 = 18400) is the minimal acceptance gate for S02; S03 adds the real regression.
