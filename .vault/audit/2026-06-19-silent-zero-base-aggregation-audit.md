---
tags:
  - '#audit'
  - '#silent-zero-base-aggregation'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-06-19-silent-zero-base-aggregation-research]]"
---

# `silent-zero-base-aggregation` audit: `Adversarial aggregation audit: cuota-side drops, recargo, annual coverage, reverse-charge symmetry`

## Scope

An adversarial pass over the IVA/renta aggregation surface, attacking failure
modes the silent-zero-base research did not cover: wrong-fact bindings, sign/flow
inversions, double-feed/double-count in totals, unconsumed cuota-bearing
categories (a real cuota silently dropped because no binding selects it — the
inverse of a silent-zero base), annual-vs-quarterly coverage asymmetry, and
reverse-charge official-box symmetry. Method: a structural scan of every compiled
modelo revision cross-referencing each ledger-bound casilla's label/role against
its binding selector's fact, flow_direction, rate_kinds, and categories; a
category-coverage subtraction (`IvaCategory` minus the cuota-less set minus the
bound set); and formula-operand tracing of the M303/M390 totals. RAG located the
sites; the registry authority and `rg` confirmed each.

## Findings

### CLEAN (adversarial checks that passed)

- No fact↔role mismatch: every M303/M390 "Cuota" casilla binds with
  `iva_amount_sum`, every "Base imponible" casilla with `base_amount_sum`.
- No rate/category misalignment: the régimen-general base casillas (01 super-
  reducido 4%, 04 reducido 10%, 07 general 21%, 28 soportado) each select the
  rate_kind and category matching their label and their sibling cuota binding;
  base and cuota bindings select the same rows under different facts, so no
  double-count.
- No resultado double-count: M303 `cuota-devengada-total` / `cuota-deducible-total`
  sum disjoint cuota casillas; the reverse-charge cuotas net to zero across the
  devengado and deducible totals as intended.
- Flow directions correct: devengado bases/cuotas use `repercutido`, deducible
  use `soportado`, self-assessed use `inversion_sujeto_pasivo`.

### HIGH — recargo de equivalencia is silently zero (M303), ADR-scale

The `recargo_equivalencia` IVA category is cuota-bearing yet **no** M303
`ledger_iva_aggregation` binding selects it; all 17 recargo casillas (bases,
tipos, cuotas at the 0.5 / 1.0 / 1.4 / 5.2 percent tiers, plus the 2024 new tier)
are manual and resolve to zero. A supplier to recargo-regime retailers therefore
under-declares the recargo it charged, with only the unrouted-observation advisory
to signal it. This is NOT a bounded mirror: the recargo rate tiers
(0.5 / 1.0 / 1.4 / 5.2 percent) are not members of `IvaRateKind`
(general / reduced / super_reduced / zero / exempt), so the existing IVA ledger
selector cannot express them. It requires a new recargo rate axis (or a dedicated
recargo aggregation source) — an ADR-scale taxonomy amendment, not a registry
binding.

### MEDIUM — M390 annual coverage of domestic reverse-charge and import is unverified, ADR-scale

The annual resumen M390 has `ledger_iva_aggregation` bindings for the main cuotas
(repercutido general/reduced/super, soportado interiores, autorepercutido
intracomunitaria) but none for `domestic_reverse_charge` or `import_third_country`,
which M303 does bind. M390 has no dedicated boxes for those flows and instead
carries a `reconciliacion-303` relation (`relation_prefill`) that reconciles the
annual totals against the M303 quarterly filings. Whether the domestic
reverse-charge and import cuotas reach the M390 resultado depends on whether that
reconciliation relation (rather than a per-flow box) is the canonical carrier.
This is the one-canonical-mechanism question and needs a decision (ledger-aggregate
those flows on M390 vs rely on the M303 reconciliation relation), not a quick
binding — so it is ADR/investigation-deferred, not a bounded mirror.

### LOW — reverse-charge official-box modelling is asymmetric (M303), net-zero-correct

Interior inversión-sujeto-pasivo is modelled with two resultado casillas
(`...interior.devengado` in the devengada total, `...interior.deducible` in the
deducible total), whereas intra-community acquisition reverse-charge is modelled
with one semantic casilla (`...intracomunitaria`, present in BOTH totals) plus two
export-only parity casillas (`...intracomunitaria.devengado` / `.deducible`) that
are excluded from the totals. Both net to zero in the resultado, so no figure is
wrong, but the two regimes use different shapes for the same concept — a
maintenance smell that invites a future double-count if the parity casillas are
ever added to a total. Harmonising them risks disturbing the official-box export
parity, so it is documented rather than changed.

### INFO — error/sentinel categories correctly unbound

`erroneous_invoice` and `unknown` are cuota-bearing-shaped but intentionally bound
by nothing; a transaction in either with a cuota raises the unrouted-observation
advisory rather than being silently aggregated, which is the correct surfacing
behaviour.

### HIGH — M100 casilla 0171 is an overloaded leaf; a direct income bind is wrong

Attempting to implement the M100 income aggregation surfaced that casilla 0171
"Ingresos de explotación" is overloaded: it is the manual income leaf AND the
target the project verb injects the M130 rendimiento neto into as a what-if
shortcut. The only M130 to M100 relation carries pagos fraccionados, not income,
so 0171 IS a genuine silent zero for a real M100 filing — but binding it directly
would reject the project-verb injection (locked source casilla) and double-path
the income against the M130 quarterly aggregation. The mechanism therefore needs
0171 disentangled (a dedicated projection leaf, or override-compatible injection)
BEFORE the income bind. ADR-scale redesign, not a bounded bind.

### MEDIUM — M390 import deducible is missing from the annual resultado

The M390 `cuota-deducible-total` sums only `soportado.interiores` and
`autorepercutido.intracomunitaria`; there is no import-deducible box and no
domestic-reverse-charge box. Domestic reverse-charge nets to zero across the
devengado and deducible totals, so its omission is harmless, but the import
deducible cuota is omitted from the deducible total only, so the M390 annual
result over-states the amount to pay for an importer. The `reconciliacion-303`
casillas are a cross-check against the summed M303 quarterly totals, NOT the
resultado carrier (correcting an earlier assumption). Fixing it requires ADDING
an import-deducible casilla (a new box, with its locale, manifest, extraction, and
formula-operand wiring), so it exceeds a bounded mirror.

## Recommendations

- Fold the recargo de equivalencia and M390 reverse-charge/import findings into the
  calculation-aggregation taxonomy ADR amendment alongside the M303 prorrata and
  M100 annual income mechanisms already recorded; none is a bounded mirror.
- Do not bind recargo with the existing IVA rate selector — it would mis-rate the
  recargo tiers; the recargo rate axis must land first.
- Leave the reverse-charge interior/intracom shapes as they are (net-zero-correct);
  track the asymmetry so no future change adds a parity casilla to a total.
- No bounded-mirror fix is available from this pass; the verified-green surface is
  unchanged.

## Codification candidates

- **Source:** the unconsumed cuota-bearing category findings (recargo, and the
  general inverse-of-silent-zero-base pattern).
  **Rule slug:** `silent-zero-base-must-aggregate-or-defer-to-adr`.
  **Rule:** A regulated base, volume, or cuota casilla whose sibling values
  aggregate from the ledger must either aggregate from its grounded canonical
  ledger source (reusing an existing `ledger_*_aggregation` family, fact, and rate
  axis) or be deferred to an ADR with a named mechanism — never left to resolve
  silently to zero, and never force-fitted onto a rate/category axis that cannot
  express it (the recargo-tier trap). This is the same candidate the ADR proposes;
  the audit corroborates it from the cuota side, not just the base side.
