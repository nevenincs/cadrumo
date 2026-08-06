---
name: iva-cuota-devengada-includes-recargo-equivalencia
---

# IVA total cuota devengada must include the recargo de equivalencia tiers

## Rule

Every IVA "total cuota devengada" aggregation formula — Modelo 303 casilla `27`,
Modelo 390 `iva.anual.cuota-devengada-total`, and any IVA modelo's total-devengada
casilla — MUST sum the recargo de equivalencia cuota tiers (recargo casillas, LIVA
art. 161) alongside the standard/reducido/super-reducido repercutido tiers and the
autorepercutido (intracomunitaria / inversión del sujeto pasivo) cuota. Omitting them
silently under-declares for any recargo filer and — because the M390 annual total is
reconciled against the summed M303 quarters — trips the
`modelo-390-cuota-devengada-total-equals-reconciliacion-303` BLOCKING_RULE.

## Why

Grounding the IVA engine against the bundled AEAT Manual Práctico IVA surfaced the same
omission twice: M303 casilla `27` never summed recargo casillas `18`/`21`/`24`, and
M390's `iva.anual.cuota-devengada-total` never summed its recargo tiers — though both
were already ledger-bound. Each silently under-declared, and the M390 case broke the
M390↔M303 reconciliation gate; both surfaced only by reconciling a manual worked example
with a recargo line against the engine. Companion to `no-silent-under-declaration` and
`ledger-iva-advisory-only-on-cuota-bearing-categories`.

## How

- **Good:** the formula sums repercutido general/reducido/super-reducido +
  autorepercutido intracomunitaria/inversión-sujeto-pasivo + the recargo tiers (LIVA
  art. 161), the construct's `legal_refs` cite art. 161, and a grounded parity test
  against a manual worked example charging recargo reproduces the printed total exactly;
  a new IVA modelo/revision confirms the aggregation enumerates every cuota-bearing tier
  including recargo and that any M390↔M303 reconciliation sees the same recargo-inclusive
  total on both sides.
- **Bad:** summing only the standard tiers and autorepercutido while omitting recargo
  (silently under-reports, desynchronises annual↔quarterly); or "fixing" a failing
  recargo-inclusive parity test with a recargo-excluded expected value — the expected
  figure is the manual's printed recargo-inclusive total; fix the formula, not the test.
