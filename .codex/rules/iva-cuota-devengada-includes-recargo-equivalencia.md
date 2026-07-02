---
name: iva-cuota-devengada-includes-recargo-equivalencia
trigger: always_on
---

# IVA total cuota devengada must include the recargo de equivalencia tiers

## Rule

Every IVA "total cuota devengada" aggregation formula — Modelo 303 casilla `27`,
Modelo 390 `iva.anual.cuota-devengada-total`, and any IVA modelo's total-devengada
casilla — MUST sum the recargo de equivalencia cuota tiers (the recargo casillas,
LIVA art. 161) alongside the standard / reducido / super-reducido IVA repercutido
tiers and the autorepercutido (intracomunitaria / inversión del sujeto pasivo)
cuota. Omitting the recargo tiers silently under-declares cuota devengada for any
filer whose supplier charged recargo de equivalencia, and — because the M390
annual total is reconciled against the summed M303 quarters — trips the
`modelo-390-cuota-devengada-total-equals-reconciliacion-303` BLOCKING_RULE for
every recargo filer.

## Why

Grounding the IVA engine against the bundled AEAT Manual Práctico IVA surfaced the
SAME omission twice: Modelo 303 casilla `27` (total cuota devengada) never summed
the recargo cuota casillas `18`/`21`/`24`, and Modelo 390's annual
`iva.anual.cuota-devengada-total` never summed its recargo tiers — even though the
recargo casillas were already ledger-bound in both. Each produced a silent
under-declaration (M303 casilla 27 short by the recargo total; M390 short by the
annual recargo total), and the M390 case additionally broke the M390↔M303
reconciliation gate for recargo filers. Both were caught only because a manual
worked example that included a recargo line was reconciled against the engine, and
both were cross-validated against the manual's own quarterly totals. This is the
IVA-aggregation companion to `no-silent-under-declaration` (an omitted tier
under-declares) and `ledger-iva-advisory-only-on-cuota-bearing-categories`
(recargo is a real cuota-bearing tier).

## How

- **Good:** the total-cuota-devengada formula sums repercutido general/reducido/
  super-reducido + autorepercutido intracomunitaria/inversión-sujeto-pasivo + the
  recargo de equivalencia cuota tiers (LIVA art. 161), and the construct's
  `legal_refs` cite art. 161. A grounded parity test against a manual worked
  example that charges recargo reproduces the manual's printed total exactly.
- **Good:** when adding a new IVA modelo or revision, confirm the total-devengada
  aggregation enumerates every cuota-bearing tier including recargo, and that any
  cross-modelo reconciliation gate (M390↔M303) sees the same recargo-inclusive
  total on both sides.
- **Bad:** a total-cuota-devengada formula that sums only the standard IVA tiers
  and autorepercutido but omits the recargo casillas — it silently under-reports
  for recargo filers and desynchronises the annual↔quarterly reconciliation.
- **Bad:** "fixing" a failing recargo-inclusive parity test by feeding the engine
  a recargo-excluded expected value — the expected figure is the AEAT manual's
  printed recargo-inclusive total; fix the formula, not the test.
