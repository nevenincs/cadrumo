---
tags:
  - '#exec'
  - '#eoy-final-calculation'
date: '2026-06-24'
modified: '2026-06-24'
step_id: 'S02'
related:
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---




# Convert casilla DP200014B:00592 to a computed casilla deriving cuota liquida from 00562 minus the grounded deduction/bonificacion casillas (each defaulting to 0)

## Scope

- `wire the owning construct and legal_refs (coordinate with the task-5 M200 owner`
- `re-read HEAD before editing)`
- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes`

## Description

- Resolved every casilla in the S01-grounded `00582`/`00592` formulas to its registry id (script-dumped to a file to bypass tool-output redaction).
- Confirmed available formula ops (`max`, `subtract`, `add`, `casilla`, `literal`) and the computed-casilla pattern (`input_kind = "computed"` + `formula = "<id>"`).
- Attempted to author `00592` as computed; the casilla-resolution surfaced a blocking modeling gap (below). Stopped rather than ship an unsafe regulated formula.

## Outcome

**S02 NOT completed — rescoped.** Converting `00592` to a computed casilla from the manual formula is NOT safely possible against the current registry model:

- **No cuota-chain `00582`.** The only casilla numbered `00582` in the M200 2024 registry is the ECPN "otras aportaciones de socios" (page 42); the cuota-íntegra-ajustada `00582` (página 14) the manual formula needs does not exist (a number-reuse collision the M200 form has across pages).
- **Number-reuse mismaps several `00592` subtrahends.** `00082` resolves to the "sociedad matriz última grupo multinacional" flag, `00399` to an ECPN "ajustes por cambio de criterio", `00590` to an ECPN casilla — not the otras-deducciones casillas the manual cites. Referencing them by bare number would subtract the wrong values (wrong corporate tax).
- **Regression risk.** Today `00592` is `input_kind = "manual"`, so a deduction-bearing filer enters their correct post-deduction cuota líquida directly. Making it computed without the full, correctly-modeled deduction chain would override that entry and over-declare.

The real fix is a substantial M200 deduction-chain modeling task: disambiguate the page-wise number reuse, add the missing cuota-chain casillas (`00582` cuota íntegra ajustada + the bonificación / doble-imposición / otras-deducciones inputs) with correct segmento + grounding against the AEAT Diseño de Registros, then author the two formulas. This exceeds a focused F2 fix and needs careful per-casilla grounding + review.

**Safe interim already in place:** `00592` stays manual and the `b06cf499f` no-silent advisory (`implies_nonzero(["DP200014:00562", "DP200014B:00599"])`) warns when cuota íntegra is positive but the final result is zero — so the silent-zero is mitigated at the notice level without risking an over-declaration regression.

## Notes

- No source was modified for S02 (the unsafe formula was not shipped); only the M200 casilla-id resolution was investigated. The plan's P01.S02 stays open with this corrected scope; P01.S03 (regression) and P02 are unaffected. Recommend re-scoping S02 into a dedicated M200-deduction-chain modeling sub-plan, coordinated with the peer-active M200 area (tasks #5/#13/#14).
