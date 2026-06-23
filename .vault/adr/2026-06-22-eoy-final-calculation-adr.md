---
tags:
  - '#adr'
  - '#eoy-final-calculation'
date: '2026-06-22'
modified: '2026-06-22'
related:
  - '[[2026-06-21-eoy-final-calculation-audit]]'
---



# `eoy-final-calculation` adr: `Annual returns must derive their headline figures (M100 income, M200 cuota liquida)` | (**status:** `accepted`)

## Problem Statement

The 2026-06-21 end-of-year final-calculation audit found that two annual self-assessment returns
silently collapse their headline figure to zero because a load-bearing casilla is left as a bare
manual input rather than derived from its upstream value:

- **F1 (M100, IRPF annual):** the annual rendimiento neto de actividades económicas was not
  aggregated — casilla 0224 resolved to 0 because no binding fed the activity income/expenses into
  the 2024 revision. (Resolved during the campaign by adding ledger income + first-slice expense
  aggregation bindings at parity with 2025; the residual non-first-slice gastos remain advisory by
  design, matching 2025.)
- **F2 (M200, IS annual):** casilla `DP200014B:00592` (cuota líquida) is declared
  `input_kind = "manual"`, so the correctly-computed cuota íntegra (`DP200014:00562`) never flows to
  cuota líquida, and the final cuota del ejercicio a ingresar (`DP200014B:00599`) silently reads 0.
  A company with €80 000 profit and a correct €18 400 cuota íntegra files €0 to pay.

Both are silent year-end under-declarations of the headline liability — the per-period engine is
sound, but the *annual aggregate* drops its result at one un-derived casilla.

## Considerations

The downstream chains are already correct: supplying `DP200014B:00592 = 18400` makes `00599` compute
to 18400.00, and the M100 income fix proved that adding the missing aggregation binding makes the
annual rendimiento appear. So the defect is narrow and local — a single missing derivation per
return — not a broken engine. The M200 cuota-líquida casilla already carries the full LIS legal_refs
set (art. 29/30/39/31/32 etc.) for the deductions/bonificaciones that reduce cuota íntegra to cuota
líquida; the formula must subtract exactly those casillas, defaulting absent deductions to 0 so a
no-deduction filer gets cuota líquida = cuota íntegra. A legitimately-zero cuota líquida (full BIN
compensation, exemptions) must remain permissible — the guard is advisory, not blocking.

## Constraints

- **Peer-active surface.** The M200 registry is being actively edited under task #5 (M202→M200 pagos
  fraccionados fold-in, just landed). The F2 change MUST be coordinated with that owner / sequenced
  to avoid clobbering uncommitted work — re-read HEAD and `git diff` the touched 200 registry files
  immediately before editing.
- **Regulated values.** The cuota-íntegra → cuota-líquida derivation must subtract the correct LIS
  deducción/bonificación casillas; an incomplete set silently over-declares, a wrong set
  under-declares. The casilla set must be grounded against the AEAT Modelo 200 Diseño de Registros /
  Manual práctico, not invented.
- **No tautological tests.** Annual regression coverage must assert against externally-grounded
  figures or structural derivation, never re-sum the aggregator's own inputs (the existing
  M130/M390 continuity tests are the template; two sibling tests under tasks #5/#11 currently trip
  the tautology gate and are out of scope here).

## Implementation

- **F2 (primary):** convert `DP200014B:00592` from `input_kind = "manual"` to a computed casilla
  whose formula derives cuota líquida from cuota íntegra (`00562`) minus the LIS bonificación /
  deducción casillas it already cites, each defaulting to 0. Wire it into the owning construct
  (satisfying the construct ⊇ casilla/binding legal-refs validator), preserving the existing
  `implies_nonzero(["DP200014:00562", "DP200014B:00599"])` advisory as defence-in-depth.
- **F1 (confirm-only):** the income + first-slice expense aggregation has landed; verify the
  non-first-slice gastos advisory fires (parity with 2025) — no further code unless the advisory is
  missing.
- **F3 (adjacent):** extend the `0004-domestic-base` M303 ledger base aggregation to every supported
  303 revision (not only `2023-y-siguientes`) so base casilla 03/07/28 never populate cuota without
  base.
- **Regression:** add real end-to-end coverage asserting each annual return reproduces its headline
  figure from period/ledger inputs (M100 annual rendimiento = Σ activity income − gastos; M200 cuota
  a ingresar = cuota íntegra − pagos), mirroring the existing M130/M390 continuity tests.

## Rationale

Grounded in the 2026-06-21 audit, whose F2 manual-casilla diagnosis was confirmed live (00592 manual
→ 00599 = 0; supply 00592 → 00599 = 18400). Deriving the headline figure rather than leaving it a
hand-entry box extends `no-silent-under-declaration` from the per-period verify gate to the year-end
aggregate, and follows the pattern the F1 income fix already established (a registry aggregation
binding at revision parity). The fix is minimal and local, so it carries low regression risk beyond
the regulated-value grounding it depends on.

## Consequences

Gains: the annual IRPF and IS returns produce a correct final liability from ledger/period inputs
instead of a silent zero; the defect class is closed with a guard that survives future revisions.
Difficulties: the cuota-líquida derivation must enumerate the correct LIS deduction/bonificación
casilla set (grounding work) and coordinate with the task-#5 M200 owner. Pitfall: an over-eager
derivation could mask a legitimately-zero cuota líquida (full BIN compensation) — keep the
zero-result path permissible and the guard advisory, not blocking.

## Codification candidates

- **Rule slug:** `annual-return-aggregates-its-headline-figure`.
  **Rule:** Every annual self-assessment modelo MUST derive its headline figure (annual
  rendimiento / base and the final cuota a ingresar) from period/ledger inputs and MUST NOT leave a
  load-bearing casilla as a bare manual input that silently resolves to zero; when a positive
  economic input is declared but the headline annual figure resolves to zero, the verify gate MUST
  surface at least an advisory. Promote after F2 lands and the lesson holds across one execution
  cycle (per the codify discipline).
