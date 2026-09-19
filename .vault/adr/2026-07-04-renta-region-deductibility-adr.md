---
tags:
  - '#adr'
  - '#renta-region-deductibility'
date: '2026-07-04'
modified: '2026-08-25'
body_hash: 'sha256:55fabda3e82cdb114e1840aa1935670e3a77dfbc71bb1229e635a6578852d86e'
related:
  - '[[2026-07-04-autonomic-deduccion-framework-adr]]'
  - '[[2026-07-01-autonomic-deduccion-auto-trigger-adr]]'
  - '[[2026-06-14-legal-grounding-centralization-audit]]'
---

# `renta-region-deductibility` adr: `region-scoped renta expense deductibility` | (**status:** `accepted`)

## Problem Statement

Plan `calculation-source-connectivity` Wave W03.P06 (Steps S33-S38) requires the
Renta ledger-expense deductibility path to become region-aware, and the parent
ADR `2026-05-20-calculation-source-connectivity-adr` explicitly deferred the
decision ("Phase 7: harden Renta region context. If category deductibility is
region-specific, key category profiles by filing year plus CCAA or regime, and
carry the selected region in the deductibility context"). Today the expense
deductibility surface is region-blind: `RentaDeductibilityContext`
(`src/aeat/domain/renta/_ledger_expenses.py`) carries `profile_year`, usage ratios,
statutory-cap axes and `exclusive_use_confirmed` but no comunidad-autonoma field;
`evaluate_renta_deductibility` and `build_renta_deductible_expense_observation`
resolve deductibility of business expenses (gastos fiscalmente deducibles) into the
first-slice Modelo 100 expense casillas; and the category-profile registry
(`src/aeat/_data/registry/aeat/categories/profiles/{2024,2025}.toml`, loaded by
`CategoryProfileRepository` keyed on `int` filing year) declares one state-level
profile per `SpendingCategory` per year, with no per-region variant.

This ADR decides four things the plan needs: (1) whether and how the comunidad
autonoma attaches to `RentaDeductibilityContext`; (2) how a region-scoped category
profile is modelled in the registry; (3) the boundary between the already-built
estatal deductibility and any autonomic layer; and (4) the behaviour when the
comunidad is undeclared but a region-scoped profile is in play.

A critical scoping fact governs the whole decision and is established up front to
prevent a duplicate mechanism. Two concepts share the word "deduction" but are
regulatorily and mechanically distinct:

- **Expense deductibility** (this surface): whether a business expense reduces the
  base imponible / rendimiento de actividades economicas. Governed by LIRPF
  arts. 28-30 (state law). Under the LOFCA / Ley 22/2009 cesion framework the
  comunidades autonomas have **no competence** over the base imponible; they cannot
  legislate which business expenses are deductible. General expense deductibility
  therefore does **not** vary by CCAA.
- **Autonomic deducciones** (a different surface, already decided): tax credits
  applied to the cuota liquida autonomica under LIRPF art. 77, legislated
  per-comunidad (nacimiento/adopcion, familia numerosa, discapacidad, ...). This is
  owned by ADR `2026-07-04-autonomic-deduccion-framework-adr` (proposed) and the
  accepted worked slice `2026-07-01-autonomic-deduccion-auto-trigger-adr`, which
  compute these credits through profile-derived-fact injection into registry
  formulas/bindings, not through the category-profile / `RentaDeductibilityContext`
  path this ADR governs.

Grounding the expense-deductibility path to art. 77 (as an initial framing
suggested) would build a second mechanism for the autonomic-cuota-deduccion concept
the framework ADR already owns -- precisely the divergence
`calculation-source-canonical-mechanism` and `no-dormant-source-resolvers` forbid.
This ADR decides the region layer for the expense path while explicitly staying out
of the art. 77 credit territory.

## Considerations

- The residence CCAA already exists as durable state and as a live registry axis.
  `TaxResidenceProfile` (`src/aeat/domain/contribuyente`) carries `ccaa: CCAA`, and
  the binding `renta-{year}-profile-tax-residence-ccaa` already projects it into the
  calc engine (consumed by the autonomic-scale formulas 0133/0134 under
  `2026-05-08-renta-cuota-integra-autonomic-scale-adr`). A region field on the
  deductibility context must reuse this axis, not invent a parallel one.
- `CCAA` is the closed `aeat.domain.contribuyente.CCAA` StrEnum: 15 ordinary
  common-regime comunidades. Foral regimes (Pais Vasco, Navarra -- own IRPF, never in
  Modelo 100) and the ciudades autonomas (Ceuta, Melilla -- art. 68.4 state cuota
  deduction) are excluded by construction (`2026-04-28-ccaa-in-profile-adr`). Any
  region key here is a value of that enum.
- `aeat-architecture-boundaries` / `aeat-schema-central-config`: the region axis is a
  closed value set (the `CCAA` enum), and every regulatory deductibility value stays
  registry TOML, never a Python literal.
- The genuinely region-varying expense-side cases are territorial **regimes** that do
  reach the base imponible, not comunidad-legislated expense rules: the Reserva para
  Inversiones en Canarias (RIC, Ley 19/1994) and Ceuta/Melilla affectation specifics.
  These are already modelled through their own dedicated bindings (e.g. the
  `ley-19-1994` RIC pathway in `trabajador_del_mar.toml`), grounded to their own
  binding law -- not through the general `SpendingCategory` profile table.
- `registry-calculation-legal-grounding` /
  `legal-grounding-verifies-bundled-authoritative-corpus`: any region-scoped profile
  variant cites the specific regime provision that fixes it (e.g. `ley-19-1994:art-27`
  for RIC), cross-checked against bundled corpus -- never a generic framework article
  and never art. 77 (which belongs to the credit path).
- `no-silent-under-declaration`: the deductibility path's honesty failure is a wrong
  base -- an over- or under-deducted expense. A region override applied against an
  unknown residence, or silently skipped, is exactly the silent-wrong-base class the
  rule forbids.
- `no-dormant-source-resolvers` / `one-aggregation-path-pull-equals-calculate`: the
  region-aware evaluation must stay on the single existing resolver
  (`ledger_renta_expense_aggregation`, `_renta_ledger.py`) that both the calculate and
  Sheets-pull paths already share; no new source kind, no second path.
- Cross-domain (W03.P07, S39-S43): fincas and inventory calculation sources are being
  provisioned as readiness-gated resolvers that emit a blocked-readiness diagnostic
  rather than resolving blank. The undeclared-region case here is the same fail-closed
  shape applied to the Renta axis, so the two decisions share one discipline (provision
  the surface, refuse visibly when a required input is absent).

## Considered options

**D1 -- How the comunidad autonoma attaches to `RentaDeductibilityContext`:**

- **A -- Add an optional `residence_ccaa: CCAA | None = None` field, sourced at the
  `_renta_ledger.py` aggregation boundary from `TaxResidenceProfile.ccaa` (the
  existing axis) (CHOSEN).** Pro: reuses the one residence-CCAA axis already bound and
  tested; optional-by-default keeps every current state-law expense evaluation
  byte-identical (satisfies S37); the field is inert unless a region-scoped profile is
  declared. Con: introduces an axis unused until the first region override lands --
  acceptable, because it is provisioned to be fail-closed, not dormant-silent.
- **B -- Make the region field mandatory on the context.** Rejected: forces a CCAA
  onto every state-law expense evaluation where region is irrelevant, and breaks the
  S37 "non-regional profiles preserve existing results" invariant.
- **C -- A new region enum / free-string region key distinct from `CCAA`.** Rejected:
  duplicates the closed `CCAA` taxonomy (`aeat-architecture-boundaries`) and
  desynchronises from the residence axis every other Renta-autonomic surface uses.

**D2 -- How a region-scoped category profile is modelled in the registry:**

- **A -- Optional per-`(filing_year, CCAA)` override layer over the year-keyed
  category-profile table, declared only for a `SpendingCategory` whose expense
  deductibility genuinely varies by a territorial regime, grounded to that regime's own
  binding law; lookup falls through to the state year profile when no override exists
  (CHOSEN).** Pro: default stays the single state profile (S37 preserved); a region
  variant is an exceptional, individually-grounded entry, not a new table per comunidad;
  keeps the concept inside the existing category-profile contract. Con: the lookup key
  widens from `int` to `(int, CCAA)`, a small repo interface change (S34).
- **B -- A full per-comunidad category-profile table (15 profile sets).** Rejected:
  manufactures region variance where state law has none, mis-grounds to a comunidad
  article for a base-imponible value the comunidad cannot set, and would re-implement
  the autonomic-deduccion concept the framework ADR already owns.
- **C -- Do not region-scope the category-profile registry at all; defer S34/S35
  indefinitely.** Rejected as the default but retained as the operative outcome for
  every category with no genuine regime variance: because no general expense
  deductibility varies by CCAA, the override layer exists but is populated only for the
  RIC/territorial-regime exceptions. This ADR provisions the mechanism (D2-A) while
  declining to populate it speculatively.

**D3 -- The estatal-vs-autonomic boundary:**

- **A -- The category-profile / `RentaDeductibilityContext` path is state
  base-imponible law (arts. 28-30); its region overrides are confined to territorial
  regimes that reach the base (RIC, Ceuta/Melilla), each grounded to its own regime
  law. The autonomic-cuota layer -- tarifa autonomica (art. 74), minimo autonomico, and
  art. 77 deducciones -- is owned by the autonomic-scale ADR and the
  deducciones-autonomicas framework ADR via profile-fact injection, and is out of scope
  here (CHOSEN).** One concept, one mechanism.
- **B -- Route autonomic-cuota deducciones through this expense-deductibility path,
  grounded to art. 77.** Rejected: a second mechanism for the framework ADR's concept;
  forbidden by `calculation-source-canonical-mechanism`.

**D4 -- Behaviour when the comunidad is undeclared:**

- **A -- Two-tier fail-closed: for a category with no region override the state year
  profile applies and an undeclared region is harmless (state law); for a category that
  does carry a region override on the applicable revision while `residence_ccaa is
  None`, the evaluation resolves `INELIGIBLE` with a determinate reason (`missing
  residence ccaa for region-scoped profile`) and surfaces an operator-facing advisory --
  never a silent grant, a silent state fallback, or a guessed region (CHOSEN).** Pro:
  honest under `no-silent-under-declaration`; mirrors the `ProfileNotConfiguredError`
  refusal the borrador/declaracion import already raises for the autonomic-scale path.
- **B -- Fall back to the state profile when the region is undeclared but an override
  exists.** Rejected: silently applies a base the operator did not choose and the law
  may not permit -- a silent wrong base.

## Constraints

- Parent stability: the residence-CCAA axis (`TaxResidenceProfile.ccaa`, the
  `renta-{year}-profile-tax-residence-ccaa` binding) is shipped and test-covered under
  two accepted/merged ADRs; this ADR consumes it and adds no new profile field. The
  category-profile registry and `RentaDeductibilityContext` are shipped surfaces; the
  change is an additive optional field plus an optional override layer, not a new
  subsystem -- no frontier risk.
- Boundary discipline is a hard constraint, not a preference: any implementation that
  reads `ley-35-2006:art-77` from this path, or emits a cuota-liquida-autonomica
  deduccion credit, is out of scope and belongs to
  `2026-07-04-autonomic-deduccion-framework-adr`. The plan must not let S33-S38 grow
  into an art. 77 credit engine.
- Grounding cost is per-override and not amortised: each region-scoped profile variant
  needs its own regime-law citation and bundled-corpus cross-check before shipping as
  filing-grade (`registry-calculation-legal-grounding`). Because the warranted set is
  small (RIC / territorial regimes), this cost is bounded, but it is real per entry.
- The `int` -> `(int, CCAA)` widening of `CategoryProfileRepository` (S34) must keep the
  pure-year lookup working unchanged for every state profile (backward-compatible key,
  not a replacement) so S37 holds.

## Implementation

Additive, on the existing single resolver -- four touch points matching the plan Steps.

1. Context axis (S33). `RentaDeductibilityContext` gains `residence_ccaa: CCAA | None =
   None` (optional, strict-frozen, default `None`). Existing evaluations that omit it
   are unchanged.
2. Source derivation (S36). The `_renta_ledger.py` aggregation boundary reads the active
   `TaxResidenceProfile.ccaa` and populates `residence_ccaa` on the context it builds --
   the same profile axis the autonomic-scale binding already consumes, so there is one
   region source of truth.
3. Region-aware profile lookup (S34/S35). `CategoryProfileRepository` accepts an optional
   `CCAA` alongside the filing year; the registry gains an optional per-CCAA override
   entry for a category, declared only for territorial-regime cases and grounded to that
   regime's own binding law. With no override, the lookup returns the state year profile
   unchanged.
4. Evaluation + fail-closed (D4). `evaluate_renta_deductibility` selects the region
   override when one exists for `(fact.category, context.residence_ccaa)`; when an
   override exists but `residence_ccaa is None`, it returns `INELIGIBLE` with the
   determinate missing-region reason and an advisory, never a silent state fallback.
5. Tests (S37/S38). S37 pins that categories with no override produce byte-identical
   results with and without a region; S38 pins that a declared region override is
   selected by the profile CCAA and that the undeclared-region case fails closed.

The cross-domain W03.P07 fincas/inventory readiness Steps (S39-S43) inherit the same
fail-closed discipline at the source-mesh boundary: a not-yet-ready resolver emits a
blocked-readiness diagnostic (per `no-dormant-source-resolvers`) rather than resolving
blank -- the region-undeclared refusal and the source-not-ready refusal are two
instances of one "provision the surface, refuse visibly" rule, which is why this ADR
feeds both phases.

## Rationale

The decision is driven by one knockout fact and one boundary. The knockout fact: under
Ley 22/2009 the comunidades autonomas have no competence over the base imponible, so
general business-expense deductibility does not vary by CCAA -- which makes Option B
under D2 (a full per-comunidad profile table) regulatorily unfounded and Option A (an
optional, individually-grounded override for genuine territorial regimes) the only shape
that matches the law. The boundary: the autonomic-cuota deduccion concept that does vary
per comunidad is already owned, end-to-end, by
`2026-07-04-autonomic-deduccion-framework-adr` and
`2026-07-01-autonomic-deduccion-auto-trigger-adr` through profile-fact injection; routing
it through this expense path (D3-B) would be a second mechanism for one concept, the exact
divergence `calculation-source-canonical-mechanism` exists to prevent. Reusing the shipped
residence-CCAA axis (D1-A) rather than a new region taxonomy keeps every Renta autonomic
surface -- scale, credits, and now the expense-override exception -- reading one region
source of truth. The fail-closed refusal (D4-A) is the same honesty gate the
autonomic-scale import path already enforces, extended to the deductibility surface so an
undeclared region can never silently pick a base.

## Consequences

- Provisions region-awareness on the Renta expense-deductibility path as an additive,
  optional, fail-closed axis over the single existing resolver -- unblocking plan Steps
  S33-S38 without a new source kind or a second aggregation path.
- Draws and records the estatal-vs-autonomic boundary explicitly, so the calc-source
  region work cannot silently grow into a duplicate of the autonomic-deduccion framework;
  a reader who arrives via "region-scoped Renta deduction" is routed to the correct
  mechanism for their concept.
- Leaves the region-override layer deliberately near-empty at first: only genuine
  territorial-regime cases (RIC / Ceuta-Melilla affectation) warrant an entry, each
  carrying its own regime-law grounding. The plan must budget per-override legal research
  and must not populate the layer speculatively.
- Accepts a small interface widening (`CategoryProfileRepository` key `int` -> `(int,
  CCAA)`) and one new optional context field; the cost is the backward-compat obligation
  that pure-year lookups and non-regional evaluations stay identical (locked by S37).
- Inherits, unresolved, the open question of whether any territorial-regime expense case
  is actually in the current filing scope; if none is, the mechanism ships
  provisioned-but-unpopulated (D2-C outcome), which is honest -- the axis is fail-closed,
  not dormant-silent -- and a future regime enrollment rides it with no further
  architectural decision.
