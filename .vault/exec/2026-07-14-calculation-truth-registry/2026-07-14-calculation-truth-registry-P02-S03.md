---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S03'
related:
  - "[[2026-07-14-calculation-truth-registry-plan]]"
---

# Build the Modelo 100 capital gains and losses calculation chain against BOE/AEAT worked examples

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/`

## Description

- Confirmed via the validated registry authority that the Modelo 100 2024 capital gains/losses chain is already BUILT: the per-transmission gain computation (casillas 1826-1840) is grounded by an existing manual-worked-example parity test, and the gains/losses aggregation and saldo netting formulas (0135-0142 into 0418-0425) exist and compute. The residual per the verification-grounding rule was independent oracle grounding of the integration/compensation (netting) layer above the per-element gain.
- Grounded that layer against the AEAT Manual practico de Renta 2024, Parte 1, Capitulo 12 (Integracion y compensacion de rentas), "Caso practico" de don A.P.G. Fed the four raw 2024 ganancia/perdida amounts at raw-input gain/loss leaves (base general ganancia 0266 4.500 / perdida 0305 9.600; base ahorro ganancia 0316 5.600 / perdida 0322 1.600) and let the live engine compute the aggregation and intra-year netting forward.
- Confirmed the engine reproduces every manual netting subtotal verbatim: base-general ganancias 4.500 (0418), perdidas 9.600 (0419), saldo neto negativo 5.100 (0421); base-ahorro ganancias 5.600 (0422), perdidas 1.600 (0423), saldo neto positivo 4.000 (0424).
- Added the oracle payload `modelo-100-2024-integracion-compensacion-ganancias-patrimoniales.json`, the parity test `test_m100_2024_integracion_compensacion_ganancias_patrimoniales_manual_worked_example.py` (grounded reproduction + a saldo-slot-flip anti-tautology check proving the max/subtract netting is evaluated + an enrollment/independently-grounded-fraction check), and enrolled the six casillas in `externally_grounded_casilla_ids` (all six were already in `reconcile_when_present_casilla_ids`).
- Repaired a latent registry inconsistency surfaced by the grounding: casilla 0529 (cuota escala autonomica sobre base liquidable general, grounded in the sibling P02.S04 commit) is computed by formula `renta-2024-cuota-escala-autonomica-sobre-base-liquidable-general` but its casilla definition omitted the `input_kind = "computed"` and `formula` back-reference fields its estatal sibling 0528 declares. Added both so the raw non-validating loader (used by the external-oracle honesty gate) sees 0529 as computed.

## Outcome

The Modelo 100 2024 capital gains/losses integration and intra-year compensation layer is now independently AEAT-grounded. Gates run green: the new parity/anti-tautology/enrollment tests, the symmetric external-oracle honesty gate `test_external_oracle_grounding_enrolled.py` (both directions, integration-marked), the registry authority load/validation tests, and 902 registry structural/M100/export/catalogue tests. The 0529 declaration fix restored the honesty gate that the sibling S04 enrollment had left latently red (the gate is integration-marked and was deselected in S04's default-marker run).

## Notes

- The per-transmission gain COMPUTATION (valor de transmision/adquisicion -> ganancia reducida, casillas 1826-1840) was already grounded by `test_m100_2024_ganancias_patrimoniales_transmision_inmueble_manual_worked_example.py`; this Step grounds the aggregation/netting layer above it, which is the genuine residual of S03's "integration and compensation" scope.
- Scoped the grounding to the current-year netting the manual prints in steps 1b/2a; the manual's downstream base imponible general (39.600) and base del ahorro (200) fold in prior-year (2020/2021) and capital-mobiliario remanente compensations this scenario does not supply, so those are deliberately not grounded here.
- Pre-existing unrelated failure observed (not owned by this Step, per full-tree-gate-must-distinguish-owner): `test_every_computed_casilla_enrolled` reports Modelo 100 2025 casilla 0501 and four Modelo 210 2025 casillas unenrolled - both are peer-owned revisions outside this Step's Modelo 100 2024 surface, left to their owners.
- The shared worktree carries extensive peer WIP (M131 fragments, irpf.toml, application tests); every commit used an explicit pathspec naming only this Step's authored files.
