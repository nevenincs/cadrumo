---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9743aacaf1b7e2f5ae3cc6874b02f04303954d5a1a3ab32b38c383b8cddf3449'
step_id: 'S13'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Decide the strength class for casillas 0529 and 0531, promoting them to the coverage-gated class raises the denominator and could flip verdicts on legitimate filings so it needs domain grounding

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100`

## Description

Decided the strength class for `0529` and `0531` at the M100 revisions 2020-2025. The two casillas take DIFFERENT classes; the asymmetry is the finding, not an oversight.

- `0529` → `externally_grounded`, already declared for revisions 2021, 2022, and 2024.
- `0531` → `reconcile_when_present` for every revision (2020-2025); no promotion.
- 2020 and 2023 carry no oracle for `0529` either and correctly remain `reconcile_when_present`: the class follows the evidence per year, not per casilla.

Registry-domain delivered the grounding and I independently re-verified it against committed HEAD before recording this closure, rather than relaying the report.

## Outcome

Enrollment was already settled before this Step: both `0529` and `0531` are enrolled as `reconcile_when_present` in the verification contract for every revision. This Step decided only the strength CLASS, and only for `0529`/`0531` — nothing here changes enrollment, and a reader must not infer the enrollment question was decided by this row.

`0529 → externally_grounded` is correct as already declared. Verified oracle figures present in `src/cadrumo/_data/corpus/manual_oracles/modelo-100-{year}-cuotas-integras-escala-aragon.json`:

| year | 0529    | 0531 | 0533    |
| ---- | ------- | ---- | ------- |
| 2021 | 2787.25 | none | 2232.25 |
| 2022 | 2667.75 | none | 2140.50 |
| 2024 | 2621.89 | none | 2094.64 |

Each year has a parity test grounding the figure against the AEAT manual worked example (`test_m100_2021_cuotas_integras_escala_aragon_manual_worked_example.py`, `test_m100_2022_...`, `test_m100_2024_...`, all present at HEAD). `0529` is present in `externally_grounded_casilla_ids` in the 2021, 2022, and 2024 `verification_expectations` TOML.

`0531 → reconcile_when_present` is correct; left unpromoted. `0531` carries no oracle figure in any year — the manual-oracle JSON files above have no `0531` key. Declaring it `externally_grounded` with no oracle would breach `verification-grounding-needs-oracle-evidence`. `0531` is absent from every `externally_grounded_casilla_ids` list at HEAD (confirmed for 2021, 2022, 2024).

`0531` does not need its own oracle: `0533 = max(0, 0529 - 0531)` (LIRPF art. 75, the registry formula `renta-2024-cuota-base-liquidable-general-autonomica`, `target_casilla_id = "0533"`), and both `0529` and `0533` are oracle-grounded, so an error in `0531` surfaces transitively at a grounded `0533`. Confirmed arithmetically for 2024: `2621.89 - 2094.64 = 527.25`.

**Caveat, recorded because it is the part that makes this honest rather than merely tidy.** The transitive grounding holds ONLY while `0529 > 0531`. The `max(0, ...)` floor absorbs an arbitrarily over-large `0531` and clamps `0533` to zero, so the oracle watches UNDER-declaration of `0531` and is blind to OVER-declaration of it. This blind spot is narrow and not reachable in the ordinary chain (escala on the base dominates escala on the mínimo, per the formula's own comment), but it is genuine and one-directional. Left as a permanent characteristic of the transitive-grounding approach, not remediated by this Step; no further action taken because promoting `0531` to `externally_grounded` without an oracle is not a legitimate close, and the blind spot is not reachable under any observed ordinary filing.

## Verification

No test run performed for this Step; it is a decision row, not an implementation row (per the plan's own closure criterion: "S13 and S16 are decisions, not implementations. They close when the decision is recorded with its grounding, including a decision to leave things as they are.").

Evidence verified by direct inspection against committed HEAD (not relayed):

- `rg -n '"0531"' src/cadrumo/_data/corpus/manual_oracles/*.json` — no match; confirms `0531` has no oracle figure in any manual-oracle fixture.
- `src/cadrumo/_data/corpus/manual_oracles/modelo-100-2024-cuotas-integras-escala-aragon.json` — `expected_by_casilla_id` contains `0529: "2621.89"`, `0533: "2094.64"`, no `0531` key.
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/{2021,2022,2024}/verification_expectations/*.toml` — `externally_grounded_casilla_ids` contains `"0529"`, does not contain `"0531"`.
- `find src/cadrumo -iname "*cuotas_integras_escala_aragon*"` — confirms the three parity tests exist (2021, 2022, 2024).
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0153-renta-2024-cuota-base-liquidable-general-autonomica.toml` — confirms `target_casilla_id = "0533"`, `expression = max(0, 0529 - 0531)`, comment already documents the LIRPF art. 75 floor.

## Notes

No incidents. No data loss. No skipped work.
