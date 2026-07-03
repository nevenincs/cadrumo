---
tags:
  - '#adr'
  - '#modelo-303-regimen-simplificado'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - '[[2026-05-27-khalid-cli-testimonial-audit]]'
  - '[[2026-04-12-modelo-303-390-adr]]'
---

# `modelo-303-regimen-simplificado` adr: `modulos-based IVA cuota binding set` | (**status:** `proposed`)

## Problem Statement

Modelo 303 has no binding set for the regimen simplificado de IVA (the modulos-based IVA
computation for estimacion-objetiva autonomos, LIVA art. 122-124). The regimen general boxes
aggregate from the ledger (`source = "ledger_iva_aggregation"` bindings for casillas
01/04/07/28 base + cuota, 59/60 intracom/export), but the entire regimen-simplificado apartado
(casillas 47, 48, 49, 50, 51-58) is authored `input_kind = "manual"` with no binding and no
formula. A filer under the regimen simplificado (every autonomo en modulos: peluquerias, bares,
taxistas, pequena restauracion) gets zero calculation help: the cuota devengada por operaciones
corrientes (box 48), the cuota derivada, and the cuota-minima floor must all be hand-computed
off-form and typed in. Because the boxes are silently manual, a filer who leaves box 48 at 0
while declaring activity produces a zero-cuota return with no gate
(`no-silent-under-declaration`). Surfaced by the Khalid persona round-11 testimonial (issue
#517, GitHub `nevenincs/aeat`; source audit `2026-05-27-khalid-cli-testimonial-audit`, task
#169). Companion to #516 (the IRPF M131 estimacion-objetiva rendimiento half of the same EO
regimen).

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

- **The computation is modulos-driven, not ledger-driven.** LIVA art. 123.Dos.1: la cuota
  devengada por operaciones corrientes se calcula aplicando a los modulos correspondientes la
  cuota derivada del metodo de estimacion objetiva. The importe per modulo unit, the cuota-minima
  percentages, and the indices correctores are published each year in the annual Orden de modulos
  (HAC/HFP), the SAME Orden that publishes the IRPF estimacion-objetiva modulos for M131. This is
  a distinct source kind from the ledger IVA aggregation; `no-dormant-source-resolvers` and
  `calculation-source-canonical-mechanism` require a canonical, enrolled resolver per source kind,
  so the simplificado value must not be forced through `ledger_iva_aggregation`.

- **Shared dataset with #516.** The annual Orden carries both an IRPF estimacion-objetiva annex
  (feeds M131 rendimiento neto, #516) and an IVA regimen-simplificado annex (feeds M303 box 48,
  #517). Both index by the same IAE activity taxonomy (already present as `legal/iae.toml`) and
  both consume the taxpayer declared modulo quantities (personal empleado, superficie, potencia
  electrica, mesas, etc.). The two engines differ in the per-activity coefficient table and the
  output (rendimiento vs cuota IVA), but the activity taxonomy, the annual-Orden dataset shape,
  and the declared-quantity capture are one foundation. The #516 owner comment already names the
  annual Orden de modulos (HAC) as its grounding, explicitly parallel to #517.

- **Casillas, corpus, and M390 fold already exist.** The simplificado casillas 47-58 are authored
  with `legal_refs = ["ley-37-1992:art-122/123/124", ...]`; the bundled corpus carries
  `ley-37-1992-art-122/123/124.html`; and the M390 box 79 fold from M303 box 54
  (`modelo-390-rel-303-cuota-devengada-simplificado`, `source = relation_prefill`) is already
  wired and tested. The gap is purely the computation feeding box 48/54, not the schema
  scaffolding around it.

- **Authoring weight.** Embedding the IVA-simplificado annex (importe del modulo, cuota minima,
  indices correctores) for every IAE epigrafe, per year, is multi-day dataset authoring; the
  owner comments on both #516 and #517 classify it as a queued campaign, not a single-pass fix.

## Considered options

- **Option A: shared modulos-data foundation feeding both M131 EO and M303 simplificado
  (recommended, phased).** One foundation feature owns the annual Orden dataset schema (both IRPF
  and IVA annexes), the IAE activity taxonomy binding, and the declared-modulo-quantity capture;
  M303 adds an IVA-simplificado engine (a `modulos_iva_aggregation` source resolver computing box
  48 via modulos x importe with the cuota-minima floor) that consumes it, and M131 (#516) adds the
  IRPF rendimiento engine over the same foundation. Pro: single authoritative modulos dataset, no
  drift between the IRPF and IVA halves, one declared-quantity surface for the filer, both engines
  enrolled canonically. Con: cross-feature coordination; the foundation must land before either
  engine.

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

- **Blocked on the shared modulos dataset (the #516/#517 joint foundation).** The IVA-simplificado
  engine cannot compute box 48 until the annual Orden IVA annex (importe del modulo, cuota minima,
  indices correctores per IAE epigrafe) is embedded as registry authority and the taxpayer declared
  modulo quantities are capturable. This dataset is the parent feature; its stability gates the
  engine phase.

- **Declared-quantity capture surface does not yet exist.** Neither M131 nor M303 currently captures
  per-activity modulo unit counts as typed profile/ledger input; the foundation must add it
  (consumed by both engines).

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

Deliver in phases. **Phase 0 (shared foundation, jointly with #516):** define the annual
Orden-de-modulos dataset as registry authority carrying both the IRPF estimacion-objetiva annex and
the IVA regimen-simplificado annex, keyed by IAE epigrafe (over the existing `legal/iae.toml`
taxonomy) and filing year; add a typed declared-modulo-quantity capture surface (per-activity unit
counts) consumed by both engines. **Phase 1 (interim, M303, single pass):** close the silent zero,
surfacing an advisory finding when the profile declares regimen-simplificado activity but box 48
resolves to zero, and expose guided manual entry for boxes 47/48, keeping them `manual` but
non-silent (Option C). **Phase 2 (M303 engine):** introduce a canonical `modulos_iva_aggregation`
source resolver, enrolled in the live calculate mesh (`merge_source_resolutions`) per
`no-dormant-source-resolvers`, that computes the per-activity cuota devengada por operaciones
corrientes (sum of modulo units x importe), applies the indices correctores, subtracts the real
cuotas soportadas por operaciones corrientes plus the 1% forfait de dificil justificacion, and
applies the cuota-minima floor (mayor de [cuota derivada; cuota minima]) to yield box 48; boxes
50/54/57/58 become `computed` formulas over 48/49/55/56, and box 47 (1T-3T ingreso a cuenta)
resolves as the Orden-declared percentage of the prior-year annual cuota derivada. **Phase 3
(parity):** confirm the existing M390 box-79 fold from box 54 reads the computed value, and add a
verify gate (advisory then blocking once computed) that box 48 is non-zero when simplificado
activity is declared. Each Orden figure carries its binding-provision `legal_refs` and a
bundled-corpus citation; the resolver and its source kind register in the enrolled-or-deferred set
so a novel binding source fails loudly rather than blanking.

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
`ledger_iva_aggregation` is rejected as the mechanism because the simplificado cuota is not a ledger
fold; forcing it through the ledger resolver would violate `calculation-source-canonical-mechanism`
(one canonical mechanism per calculation type).

## Consequences

- **Unblocks the EO/modulos filer population** (a large share of autonomos) for IVA filing, the same
  population #516 unblocks for IRPF, over one coordinated dataset.
- **Removes the silent zero immediately** (Phase 1) even before the engine lands, so no EO filer
  files a zero-cuota IVA return unwarned.
- **Introduces a new source kind (`modulos_iva_aggregation`)** and a per-year regulatory dataset;
  both add authoring and maintenance surface. The Orden republishes annually, so the dataset carries
  a standing yearly update cost shared with #516.
- **Cross-feature dependency risk:** the M303 engine phase cannot close until the shared foundation
  lands; if #516 and #517 are scheduled independently the foundation must be explicitly owned by one
  of them (or a dedicated parent feature) to avoid each waiting on the other. Recommend a single
  parent feature (`eo-modulos-orden-dataset`) that both depend on.
- **Declared-quantity capture becomes a new operator input surface** that must be typed, validated,
  and persisted per profile/activity: a new persistence-boundary and CLI surface.
- **Corpus debt:** the annual Orden modulo annexes are not yet bundled; each filing-year Orden must
  be added to the corpus and cross-checked before its figures ship
  (`legal-grounding-verifies-bundled-authoritative-corpus`).
