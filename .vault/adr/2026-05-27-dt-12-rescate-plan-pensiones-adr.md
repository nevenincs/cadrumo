---
tags:
  - '#adr'
  - '#dt-12-rescate-plan-pensiones'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-04-21-modelo-100-renta-adr]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
  - "[[2026-05-07-renta-full-coverage-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - '[[2026-06-04-dt-12-rescate-plan-pensiones-research]]'
---


# `dt-12-rescate-plan-pensiones` adr: DT 12a rescate plan pensiones capital reduccion | (**status:** `accepted`)

## D1 — Context

Carla (round-19) retired and rescued her occupational pension plan (`plan de
pensiones`) as a lump-sum capital payment. Under LIRPF Disposición Transitoria
12ª (DT 12ª), contributions made before January 1 2007 to a pension plan or
`mutualidad de previsión social` are eligible for a 40% reduction on the
portion of the lump-sum attributable to those pre-2007 contributions.

This reduction is a significant deduction for the approximately 1 million
retirees who made pre-2007 pension contributions. Without it, Carla's M100
IRPF liability would be materially overstated.

Prior to this ADR `work calculate` had no mechanism for the operator to supply
the split between pre-2007 and total contributions. The casilla 0011
(rendimientos íntegros del trabajo reducidos) had no semantic-role binding
for the DT 12ª reduction, and the application emitted no advisory when a high
rendimientos_integro amount was paired with a zero reduction, despite the
likely eligibility.

Legal grounding: LIRPF Disposición Transitoria 12ª; RIRPF art. 17;
DGT binding consultations on application of the 40% reduction.

## D2 — Decision

### D2.1 — Add three dedicated CLI flags on `work calculate`

Add:
- `--rescate-plan-pensiones-capital` — the gross lump-sum capital payment
  received from the pension plan.
- `--rescate-plan-pensiones-aportaciones-pre-2007` — the euro amount of
  contributions made before January 1 2007.
- `--rescate-plan-pensiones-aportaciones-totales` — total contributions over
  the plan's life.

All three flags are `Decimal | None`. When the first flag is supplied, all
three must be present; the CLI emits a `BadParameter` if only a subset is
provided.

### D2.2 — Pure helper `_compute_dt12_reduccion_plan_pensiones`

Add a pure helper function `_compute_dt12_reduccion_plan_pensiones(
capital, pre_2007, totales) -> Decimal` in
`src/aeat/application/modelo/_actions.py`. The formula is:

  `reduction = (pre_2007 / totales) * capital * Decimal("0.40")`

Rounding: `ROUND_HALF_UP` to 2 decimal places (monetary precision).

### D2.3 — Semantic-role injection into casilla 0011

The computed reduction is injected into the M100 casilla that carries the
`semantic_role = "rendimiento_trabajo_reduccion_dt12"` via the existing
semantic-role lookup in `work calculate`. This avoids hard-coding the casilla
number in application code; the registry entry for casilla 0011 (or its
successor in future revision) carries the semantic role.

### D2.4 — Advisory for likely-eligible operators

Emit a `DT_12A_REDUCCION_POSSIBLE` advisory WARNING when
`ingreso_integro > 20_000` and the computed reduction is zero (i.e., the
flags were not supplied). This threshold is a conservative heuristic — lump-
sum pension rescues at above €20,000 are very likely to have pre-2007
contributions; below that amount the reduction may not be material.

## D3 — Alternatives considered

**Alternative A: profile field for pension pre-2007 split.** Store
`plan_pensiones_pre_2007_fraction: Decimal | None` on `TaxpayerProfile` so
the split is remembered across recalculations. Rejected for this ADR: DT 12ª
applies only in the year of rescue; storing it permanently on the profile
would confuse operators in subsequent years. The `work calculate` transient
flags are the correct surface for a one-time election.

**Alternative B: derive from transaction ledger.** Future work could identify
the lump-sum pension payment from the transaction ledger (once bank statement
import supports pension custodian sources). Rejected for this ADR: the ledger
does not yet classify pension rescue payments; operator supply is the
authoritative mechanism until ledger classification is implemented.

**Alternative C: casilla 0011 direct binding without semantic role.** Hard-
code casilla 0011 in the application action. Rejected: the no-hard-coded-
casilla rule requires that application code reference casillas through
semantic roles so registry renumbering does not break the application.

## D4 — Trade-offs

- **One-time vs persistent.** Treating the three flags as transient `work
  calculate` inputs rather than profile fields means the operator must re-
  supply them if they recalculate. This is the correct trade-off: DT 12ª
  elections are filing-period-specific and should not silently persist into
  the following year's default profile.
- **Advisory threshold accuracy.** The €20,000 heuristic for the advisory
  will produce false positives for some operators (small pension rescues
  with no pre-2007 contributions) but is unlikely to produce false negatives
  for the primary affected population of retirees. A stricter threshold
  would miss eligible operators.
- **ROUND_HALF_UP for tax reduction.** The AEAT workbooks use ROUND_HALF_UP
  for rendimiento reductions. Applying the same rounding mode ensures
  consistency with the oracle oracle case for Carla (9600/33000 × 60000 × 40%
  = €6,981.82).

## D5 — Consequences

- `work calculate` gains three optional co-required flags for DT 12ª rescue.
- The `_compute_dt12_reduccion_plan_pensiones` pure helper is the canonical
  implementation; it is unit-testable without CLI machinery.
- The oracle test for Carla (€9,600/€33,000 × €60,000 × 40% = €6,981.82) and
  an anti-tautology proof test are added.
- Approximately 1 million retirees with pre-2007 pension contributions are
  now correctly served by the application's M100 calculation path.
