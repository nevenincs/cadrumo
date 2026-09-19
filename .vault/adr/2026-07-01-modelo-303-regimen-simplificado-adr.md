---
tags:
  - "#adr"
  - "#modelo-303-regimen-simplificado"
date: '2026-07-01'
related:
  - "[[2026-07-10-modelo-303-regimen-simplificado-research]]"
modified: '2026-08-28'
body_hash: 'sha256:6aba295285d5e88a85bd35c193ebdafc1164b11ca44da433029770413bd09380'
---
# `modelo-303-regimen-simplificado` adr: `modulos-based IVA cuota binding set` | (**status:** `accepted`)

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

- **Per-year parameter authority is distinct from law-selected M303 design epochs.** M131 is
  already authored per-year (`2024`, `2025`, `2026`) because modulos change annually; the M303
  simplificado engine inherits the same parameter cadence, so the resolver must select the Orden
  dataset by filing year. M303 independently selects one of the five explicit modern design
  bindings (`2023`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t`, `2025`, or
  `2026-y-siguientes`) from the legal filing year and period. The retired spanning revision is not
  a fallback. The per-year modulo dataset remains a separate authority and does not create another
  M303 design revision.

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

## Amendment (2026-08-11): S59 annual Orden authority

S59 supersedes this record's partial-catalogue and missing-corpus premises, but not its separate casilla-48 calculation-completeness constraint. The canonical registry now compiles the complete Annex II IVA annual-quota taxonomy independently for 2023, 2024, 2025, and 2026 from each year's hash-pinned BOE HTML: exactly 49 activity tables and 141 module rows per year. `ActividadOrdenAnualId` is the duplicate-safe activity identity; raw IAE, activity kind, table ordinal, and caller-supplied Orden tuples are not selectors.

One production-neutral DOM parser supplies immutable table IR to both the registry compiler and the documentation preprocessor. The preprocessor deterministically regenerates the canonical `.extracted.json` and `.extracted.md` sidecar pairs with semantic Annex II anchors. Generated table-scoped legal references enter the ordinary legal catalogue and retain their normative source identity and digest; hash anchors, ordinal anchors, hand-authored table maps, incomplete sidecars, and parallel runtime authority are forbidden. The manifest and preprocessing check gates refuse stale hashes, extractor-version drift, missing or extra tables, duplicate or ambiguous anchors, cross-year contamination, malformed or truncated sources, unconsumed authority files, and divergence in either member of a sidecar pair.

The annual Orden dataset is therefore no longer a blocker or a manually maintained first slice. Official casilla 48 remains manual only for the independent taxpayer-evidence and full calculation-completeness conditions retained by this ADR; no partial catalogue claim may justify a second resolver, silent zero, or fallback.

S59 does not infer or attest positive censal applicability. Its required closed typed scope input is deliberately narrower: not-claimed is neutral and must reject Orden/module rows, while evidence-required refuses before calculation or export until S58 supplies evidence. S59 does not derive that input from a taxpayer profile and owns no IVA regime-composition enum. S55 exclusively owns the required persisted `ModeloIVAProfile` composition and its exact mapping into the S59 scope input, with no default, backfill, or string coercion. S58 alone owns the nominal filing-evidence reference and the immutable, evidence-bearing applicability captured when a calculation revision is created. The annual Orden snapshot may validate a referenced activity after that evidence exists; it cannot manufacture censo facts or become a second evidence owner.

## Amendment (2026-08-13): complete calculation and value-arrival authority

The decision is now accepted. S59 removed the annual-Orden catalogue and corpus blockers, while S58 established immutable evidence-bearing applicability. The remaining filing-critical work is one complete calculation and value-arrival authority for every official DP30302 simplified-regime semantic value; structural field enumeration and projection declarations cannot substitute for it.

The annual Orden snapshot remains the sole authority for activity taxonomy, annual module identity and order, coefficients, minimum-quota percentages, legal references, and source digests. It owns no taxpayer quantities or filing results. Immutable `RegimenSimplificadoFilingRows` remain the sole owner of taxpayer-declared activity and module inputs, each bound to exact filing evidence. One calculation-domain per-activity result owns all derived agricultural and non-agricultural values for the selected year, revision, period, and Orden snapshot. The result retains ordered evidence references, source and legal provenance, calculation-revision identity, and a deterministic digest.

The existing registry calculation mechanism is extended atomically; no export-specific calculator, generic fact string, open result bag, parallel resolver, or per-slot scalar store is admitted. Values that law leaves as taxpayer statements remain explicit attested inputs. Values determined from those inputs and annual parameters are produced only by the canonical calculation service. `M303FilingFacts` and `FilingProducerSnapshot` carry the immutable result beside the filing rows and Orden snapshot. Projection selects a typed semantic value from that result and performs no formula, inference, default, or fallback.

Before implementation, one reviewed five-epoch field matrix classifies every DP30302 semantic field as identity, declared input, attested off-form input, calculated output, or source-proven inapplicable. Applicable rows require complete evidence and exactly one matching calculation result. Wrong-year, wrong-revision, wrong-period, extraneous, duplicate, incomplete, or digest-divergent results refuse the whole export before any target is created. Non-applicability is decided only by the canonical typed scope decision.

The partial 34-endpoint completeness assumption is withdrawn. Generic `off_form_result` paths that duplicate a typed calculated result are deleted in the same cutover. Blank and zero are never missing-value defaults, and no compatibility reader, alias, layout-derived semantic, or partial historical calculation survives.

## Amendment (2026-08-13): S74 calculation-mechanism collapse

For avoidance of doubt, the "existing registry calculation mechanism" retained by the preceding amendment is the calculation-domain, per-activity mechanism over immutable `RegimenSimplificadoFilingRows` and the exact `M303AnnualOrdenSnapshot`. It is not the generic casilla-leaf formula-runtime path. The calculation service owns derived agricultural and non-agricultural values; `project_m303_regimen_simplificado_rows` remains a coordinate-only selector over typed inputs and typed calculated results and must not acquire formula, annual-parameter lookup, inference, aggregation, default, or fallback behavior.

The casilla-leaf channel is retired atomically. The two M303-specific formula operators, their operator vocabulary and arity contracts, evaluator dispatch and helpers, formula-evaluation context, generic calculation API arguments and transitive caller plumbing are deleted. Across every explicit modern M303 revision, the ten internal single-activity support casillas, their two formulas, construct membership, completeness-manifest declarations, and reconcile-when-present entries are deleted together. Spreadsheet handling and tests that name or preserve those operators are removed or retargeted to the row-indexed calculation contract. No re-export, adapter, compatibility reader, dormant dispatch, or parallel resolver survives.

The annual-Orden compiler, immutable snapshot, typed scope decision, filing evidence, filing rows, projection-reference union, and row projector remain canonical foundations. S74 does not delete the transitional `off_form_result` member or its admitted projection endpoints ahead of replacement: S76 must first provide the complete typed per-activity calculated result, and S77 deletes that generic value path in the same atomic cutover. S75 first closes activity identity so the canonical calculation cannot select ambiguously. S76 then binds each result to year, law-selected revision, period, evidence, legal and source provenance, and deterministic digest. S77 completes the one-way migration with no alias, fallback, historical partial calculation, or missing-value zero.

This amendment supersedes the earlier statements in this record that assign calculation ownership to the generic formula runtime or propose promotion of its single-activity support casillas to official casilla 48. The annual Orden remains registry authority; the calculation owner is row-indexed and calculation-domain; projection remains selection-only.

## Amendment (2026-08-14): S84 immutable Modelo 390 annual-summary handoff

The canonical cross-model owner is one application-calculation handoff assembler invoked while calculating the annual Modelo 390. It consumes the persisted fourth-quarter Modelo 303 `CalculationRevision`, its immutable filing-instance evidence, and the exact `M303RegimenSimplificadoCalculationResult`; it does not consume a scalar filing observation, a `relation_prefill` value, an export projection, or a reconstructed registry formula. The 2022 source coordinate and unavailable agricultural crosswalk are grounded by `2026-08-13-aeat-export-fragment-generator-authority-m303-2022-orden-crosswalk-lorca-reference`, and S83's retained refusal is part of this decision rather than an omitted value.

The handoff carries exactly ten typed money values. Modelo 390 boxes 74 and 75 are respectively the sums of `cuota_resultante` over the non-agricultural and agricultural cohorts in the one canonical per-activity result. The remaining values are selected without recalculation from the same source revision: box 76 from Modelo 303 box 51, box 77 from box 53, box 78 from box 52, box 79 from box 54, box 80 from box 55, box 81 from box 56, box 82 from box 57, and box 83 from box 58. The non-sequential 51, 53, 52 order is official meaning, not a sortable mapping. Boxes 74-83 remain canonical Modelo 390 `CasillaId` endpoints; the handoff supplies value arrival and does not create shadow official-box identifiers.

One frozen handoff is persisted on the target Modelo 390 `CalculationRevision` as a calculation input and participates in its content-addressed identity. Its canonical payload carries all ten values; the source bucket, Modelo 303 work-unit id, calculation-revision id, law-selected registry revision, filing year and period `4T`; the exact simplified-result digest and ordered evidence identities; and the target bucket, Modelo 390 work-unit id, selected registry revision, filing year, and annual period. The handoff digest covers that payload but excludes itself and the target calculation-revision id. The target calculation-revision id is derived with the unsigned handoff payload, then stamped on the frozen handoff and required to equal its containing revision. This is the only admitted non-self-referential construction of strict target calculation identity.

Assembly joins through the secure work-unit, calculation-revision, and filing-record catalogues. The source and target must belong to the same bucket and filing year; the target must be Modelo 390 period `0A`; the source work unit must be Modelo 303 period `4T`. S84 admits only the source work unit's `filed_calculation_revision_id`: it must be non-null, resolve under that work unit to state `PRESENTADO`, and equal `current_calculation_revision_id`; `current_filing_record_id` must resolve to the current filed record for that same calculation revision. A merely `VERIFICADO_COMPLETO` current revision, the generic export-selector precedence, an unambiguous-revision search, and a `PRESENTADO_SUPERSEDIDO` revision are not admitted. If current and filed calculation pointers differ—including a new draft or verified amendment after the filed return—the assembler refuses until one current filing advances both pointers together; it never silently continues with the older filed result or substitutes the newer unfiled result. The admitted revision's work-unit id, registry revision, period, filing record and filing-instance evidence, simplified result, result digest, ordered evidence identities, and eight source casilla values must all agree. A missing, duplicate, stale, foreign-bucket, wrong-year, wrong-period, wrong-revision, superseded-pointer, evidence-divergent, value-divergent, or digest-divergent source refuses before target revision persistence or export. An arbitrary observation timestamp, latest-record search, scalar relation selector, manual Modelo 390 override, or fallback to a different Modelo 303 revision is not identity.

S83 deliberately retains an evidence-bearing `AutoridadAgricolaOrdenAnualNoResuelta` because the official annual Orden and DP30302 design do not publish the required two-digit agricultural crosswalk. Therefore an agricultural source row cannot produce a partial handoff and box 75 cannot default to zero. The assembler raises the typed S83 refusal until a later accepted amendment and source-grounded calculation result resolve that cohort. Zero for box 75 is admitted only when the immutable filing rows and complete canonical result positively prove that the agricultural cohort is empty. This is not a new prerequisite step for S84: explicit refusal is the supported current authority state. The handoff contract remains capable of carrying agricultural results when that authority later exists.

Modelo 390 projection is selection-only. It selects the ten typed handoff members into boxes 74-83 and performs no formula, cohort aggregation, source-casilla lookup, annual-Orden lookup, inference, default, or fallback. Assembly validates box 79 against source box 54 and retains the source-declared box 54, 57, and 58 arithmetic coherence; projection does not recompute those totals.

The replacement is atomic. The scalar relation `modelo-390-rel-303-cuota-devengada-simplificado`, binding `modelo-390-prev-303-cuota-devengada-simplificado`, relation declaration, binding declaration, box-79 binding edge, construct and dependency references, scalar-fold tests, manual binding overrides, and fixtures that seed or preserve the scalar path are deleted in the same change that admits all ten typed values. Box 79 itself, its canonical continuity identity, completeness membership, and official Modelo 390 meaning remain and are retargeted to the typed handoff together with boxes 74-78 and 80-83. Structural gates reject both retired identifiers and any equivalent Modelo-303-box-54 scalar relation. No alias, compatibility reader, dual arrival path, or temporary box-79 bridge survives.

This amendment refines this accepted record because it owns the one simplified-regime calculation result and its downstream value arrival. The generator-authority ADR continues to own source coordinates, semantic maps, render profiles, and emitted wire composition; it requires no amendment for this application value-arrival contract. A sibling ADR would split one calculation decision and is rejected.

## Amendment (2026-08-28): the annual-summary handoff is conditional on the regime reaching the taxpayer

S84 established the immutable Modelo 390 annual-summary handoff and its arrival path. It did not settle WHO the handoff is required of, and the omission had teeth: applicability was keyed on the registry revision alone, so the annual-summary requirement projected non-empty whenever the binding family was declared, the resolver then demanded exactly one filed same-bucket Modelo 303 `4T` work unit, and the calculate-path guard enforced a strict biconditional between declaration and handoff presence. Boxes 74-83 ride on EVERY Modelo 390 form, so every epoch declares the family, and the deleted `2010-y-siguientes` revision declared it too. The effect was that a regimen general filer was routed through a regimen simplificado source it can never possess -- and Modelo 390 is the IVA resumen anual, whose majority population is exactly that filer.

LIVA art. 122 Uno, read in the bundled consolidated corpus, states that the regime `se aplicara a los sujetos pasivos ... que reunan los siguientes requisitos` and then lists three: personas fisicas or entidades en regimen de atribucion de rentas whose members are all personas fisicas, activities determined by regulation, and a prior-year volume-of-operations limit. Applicability is therefore a taxpayer fact, not a form fact. A revision declaring the family says what the FORM carries, never that the regime reaches this filer.

This record already owns the vocabulary that expresses the judgement, and this amendment only enrolls its last call site. The closed scope carries not-claimed and evidence-required; the composition mapping sends GENERAL to not-claimed and SIMPLIFIED and MIXED to evidence-required, refusing an unknown composition rather than defaulting. Four production sites already gated on not-claimed while the annual-summary requirement consulted none of it. Not-claimed remains neutral: it rejects Orden and module rows, and it now equally withholds the annual-summary handoff.

The derivation is single-homed beside the other scope derivations and is SUPPLIED to its consumers rather than reached for, because the closed vocabulary lives in the modelo package and the annual-summary resolver does not: the resolver receives an applicability flag exactly as the simplificado calculation surface already receives its scope decision, adding no cross-package edge. Four sites consult that one derivation. The resolver returns an empty resolution when the regime does not reach the filer. The calculate guard's antecedent widens from declaration to declaration AND applicability, carrying both facts into its refusal context so a diagnostic says which half failed. The persisted-target validator treats inapplicable exactly as undeclared, since neither state can produce a handoff, making an absent handoff correct and a persisted one equally anomalous. Verification passes the same derivation.

The arrival-path invariant S84 established is unchanged, and is not what moved. A missing, unexpected, stale, divergent, or superseded handoff is still refused wherever the regime does reach the taxpayer; the biconditional still binds, on a corrected antecedent. Widening it to admit a handoff that arrived by some other route would have been the loosening this decision refuses.

One question is deliberately left open and must not be silently folded into this one. A Modelo 390 calculation still hard-requires a filed Modelo 303 `4T` work unit wherever the family applies, and it is defensible that an annual resumen presupposes the year's quarterly autoliquidaciones. What this amendment settles is only that the SIMPLIFICADO resolver must not be the mechanism enforcing that presupposition against a taxpayer the regime does not reach. A general prerequisite on the quarterly chain needs its own decision and its own owner.
