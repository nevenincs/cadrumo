---
tags:
  - '#adr'
  - '#modelo-303-regimen-simplificado'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:2a14228e1b466b5e99e91babbba5f826a2c5daf3796a53cb8e706c9176d38533'
related:
  - '[[2026-05-27-khalid-cli-testimonial-audit]]'
  - '[[2026-04-12-modelo-303-390-adr]]'
  - '[[2026-07-10-modelo-303-regimen-simplificado-research]]'
---

# `modelo-303-regimen-simplificado` adr: `modulos-based IVA cuota binding set` | (**status:** `proposed`)

## Problem Statement

Modelo 303 now has a first, registry-computed regimen-simplificado reference path for tabled
2025 IAE activities. Support casillas capture an epigrafe and up to three modulo quantities;
`m303_resolve_modulos_iva_cuota_devengada` and
`m303_resolve_modulos_iva_cuota_minima_pct` consume the annual coefficient tables; and
`modulos-iva-cuota-derivada` applies the difficult-justification forfait and minimum floor. A
verification advisory compares that computed reference with official casilla 48.

The remaining gap is narrower but filing-critical: official casilla 48 remains manual because
the first slice neither captures the taxpayer's real cuotas soportadas por operaciones
corrientes nor covers the full activity/year catalogue. The code must not silently substitute
the partial reference into the filed total. This ADR remains proposed to decide and deliver that
last-mile authority without creating a second calculation path.

## Considerations

- **The 303 form surfaces only totals; the per-activity computation is off-form.** The official
  Modelo 303 regimen-simplificado apartado carries the aggregate boxes (47 = suma ingresos a
  cuenta 1T-3T, 48 = suma cuotas derivadas del regimen simplificado del conjunto de actividades,
  49 = ingresos a cuenta realizados, 50 = resultado 4T [48]-[49], 54 = total cuota resultante,
  55-57 IVA deducible de activos fijos, 58 = resultado). The per-activity modulo detail (numero
  de unidades de cada modulo x importe del modulo, indices correctores, cuota minima, 1% forfait
  de cuotas soportadas de dificil justificacion) is computed on the AEAT off-form worksheet
  (hoja de calculo / anexo del regimen simplificado del IVA) and only the total reaches box 48.
  Modelling the regimen simplificado therefore means modelling a computation whose inputs are
  NOT on the 303 form itself.

- **The computation is modulos-driven and already registry-formula-driven, not ledger-driven.**
  LIVA art. 123.Dos.1: la cuota
  devengada por operaciones corrientes se calcula aplicando a los modulos correspondientes la
  cuota derivada del metodo de estimacion objetiva. The importe per modulo unit, the cuota-minima
  percentages, and the indices correctores are published each year in the annual Orden de modulos
  (HAC/HFP), the SAME Orden that publishes the IRPF estimacion-objetiva modulos for M131. This is
  distinct from ledger IVA aggregation. The live canonical mechanism is the registry formula
  runtime and its table parameters. `calculation-source-canonical-mechanism` therefore forbids
  adding a parallel `modulos_iva_aggregation` resolver for the same calculation; the existing
  formula path must be extended or explicitly replaced in one atomic migration.

- **Shared authority with #516, with a first M303 slice already enrolled.** The annual Orden
  carries both an IRPF estimacion-objetiva annex
  (feeds M131 rendimiento neto, #516) and an IVA regimen-simplificado annex (feeds M303 box 48,
  #517). Both index by the same IAE activity taxonomy (already present as `legal/iae.toml`) and
  both consume taxpayer-declared modulo quantities (personal empleado, superficie, potencia
  electrica, mesas, etc.). M303 already captures the first three slots in internal support
  casillas and enrolls the 2025 tabled coefficient slice. The two engines differ in the
  per-activity coefficient table and the
  output (rendimiento vs cuota IVA), but the activity taxonomy, the annual-Orden dataset shape,
  and the declared-quantity capture are one foundation. The #516 owner comment already names the
  annual Orden de modulos (HAC) as its grounding, explicitly parallel to #517.

- **Official casillas, computed support casillas, corpus, and M390 fold exist.** The
  simplificado casillas 47-58 are authored
  with `legal_refs = ["ley-37-1992:art-122/123/124", ...]`; the bundled corpus carries
  `ley-37-1992-art-122/123/124.html`; and the M390 box 79 fold from M303 box 54
  (`modelo-390-rel-303-cuota-devengada-simplificado`, `source = relation_prefill`) is already
  wired and tested. The remaining gap is promotion of the partial computed reference into a
  complete, officially grounded casilla-48 calculation after real soportado inputs and full
  activity/year coverage exist.

- **Authoring weight.** Embedding the IVA-simplificado annex (importe del modulo, cuota minima,
  indices correctores) for every IAE epigrafe, per year, is multi-day dataset authoring; the
  owner comments on both #516 and #517 classify it as a queued campaign, not a single-pass fix.

## Considered options

- **Option A: extend the enrolled registry-formula mechanism to official casilla 48
  (recommended, phased).** Complete the annual Orden tables and declared inputs used by the live
  `modulos-iva-*` support casillas/formulas, add real cuotas-soportadas evidence, then promote the
  same formula result to casilla 48. Pro: one calculation authority, no formula/resolver split,
  and the existing discrepancy advisory remains an honest guard until coverage is complete. Con:
  the official-box promotion cannot precede full input and authority coverage.

- **Option B: simplificado-only, duplicate the Orden dataset inside M303.** Author the IVA annex
  tables privately under the M303 registry, independent of #516. Rejected: duplicates the same
  annual Orden that #516 must also embed, splits the activity taxonomy, and drifts the two halves
  every year the Orden changes, exactly the scatter `aeat-schema-central-config` forbids.

- **Option C: interim non-silent surface + guided manual entry (recommended as Phase 1).** Keep
  boxes 47/48 manual for now but close the silent-zero: surface an advisory when regimen-simplificado
  activity is declared with box 48 at zero, and guide the operator through the off-form modulo
  computation. Pro: removes the `no-silent-under-declaration` breach immediately, ships in one pass,
  unblocks EO filers with an honest manual path while the dataset is authored. Con: not yet a
  computation; the filer still hand-computes the modulo cuota.

- **Option D: leave the boxes silently manual (status quo).** Rejected: an EO filer files a
  zero-cuota IVA return on positive module-based activity with no gate; this is the exact defect
  #517 reports.

## Constraints

- **Partial authority must not masquerade as complete authority.** The 2025 first-slice tables and
  three declared-unit support casillas are live. Casilla 48 must stay manual until the activity
  catalogue, relevant module slots, indices and real cuotas-soportadas inputs needed for the
  official result are complete and registry-grounded.

- **One mechanism only.** The current registry formula runtime is the calculation owner. A new
  `modulos_iva_aggregation` source resolver is prohibited unless an approved ADR explicitly
  replaces and removes the formula path in the same change.

- **Per-year revision granularity.** M131 is already authored per-year (`2024`, `2025`, `2026`)
  because modulos change annually; the M303 simplificado engine inherits the same per-year dataset
  cadence, so the resolver must resolve the Orden dataset by filing year. Note M303 uses two coarse
  revisions (`2009-y-siguientes` inline, `2023-y-siguientes` fragmented); both must be read per
  `registry-revision-content-inline-or-fragmented`. The per-year modulo dataset is a separate
  authority the resolver keys into, not a new M303 revision per year.

- **Grounding must be the annual Orden against bundled corpus.** Each importe/cuota-minima figure is
  a regulatory value and must cite the specific Orden article per
  `registry-calculation-legal-grounding`, not only the framework LIVA art. 123; the annual Orden
  text must be bundled and cross-checked per `legal-grounding-verifies-bundled-authoritative-corpus`
  (the framework art. 122-124 corpus is present; the annual Orden modulo annex is not yet).

## Implementation

Continue the shipped formula path in phases. **Phase 1 (current):** retain manual official
casilla 48, the table-driven `modulos-iva-cuota-devengada` /
`modulos-iva-cuota-derivada` reference, and the non-silent discrepancy advisory. **Phase 2
(coverage):** extend the filing-year Orden tables, module quantity inputs and indices to the
supported activity catalogue; add typed, persisted evidence for real cuotas soportadas por
operaciones corrientes. **Phase 3 (promotion):** only when coverage is complete, bind official
casilla 48 to the existing registry formula result, make dependent official boxes computed where
their legal structure permits, and retain parity tests against M390 box 79. Each Orden figure
carries binding-provision `legal_refs` and bundled-corpus evidence. No parallel source resolver is
introduced.

## Rationale

The decision is Option A for the dataset foundation plus Option C as the interim M303 surface,
because the two issues (#516 IRPF, #517 IVA) are two consumers of one regulatory artifact, the
annual Orden de modulos, and authoring that artifact twice would guarantee drift between the IRPF
and IVA halves each year the Orden is republished, contradicting `aeat-schema-central-config`. A
shared foundation makes the Orden dataset, the IAE taxonomy, and the filer declared quantities
single-sourced and consumed by both engines. The computation follows LIVA art. 123.Dos verbatim
(metodo de indices, modulos u otros parametros objetivos; cuota devengada por operaciones corrientes
minus deducibles), so the engine is grounded in law, not invented (`aeat-safety-legal-gates`).
Option C ships first because the dataset authoring is multi-day and an EO filer must not be left with
a silently zero return in the interim (`no-silent-under-declaration`); it is the honest
defect-of-record surface the source audit Recommendations section already anticipated.
`ledger_iva_aggregation` is rejected because the simplificado cuota is not a ledger fold. A new
`modulos_iva_aggregation` resolver is also rejected now because the registry formula runtime
already owns this calculation; either parallel path would violate
`calculation-source-canonical-mechanism`.

## Consequences

- **Unblocks the EO/modulos filer population** (a large share of autonomos) for IVA filing, the same
  population #516 unblocks for IRPF, over one coordinated dataset.
- **Removes the silent zero immediately** (Phase 1) even before the engine lands, so no EO filer
  files a zero-cuota IVA return unwarned.
- **Extends the existing registry formula and per-year regulatory dataset.** The Orden republishes
  annually, so the dataset carries a standing yearly update cost shared with #516; no new source
  kind is created.
- **Cross-feature dependency risk:** the M303 engine phase cannot close until the shared foundation
  lands; if #516 and #517 are scheduled independently the foundation must be explicitly owned by one
  of them (or a dedicated parent feature) to avoid each waiting on the other. Recommend a single
  parent feature (`eo-modulos-orden-dataset`) that both depend on.
- **Declared-quantity capture already exists for the first slice** and must be extended, validated
  and persisted for the complete supported activity/module catalogue.
- **Corpus debt:** the annual Orden modulo annexes are not yet bundled; each filing-year Orden must
  be added to the corpus and cross-checked before its figures ship
  (`legal-grounding-verifies-bundled-authoritative-corpus`).
