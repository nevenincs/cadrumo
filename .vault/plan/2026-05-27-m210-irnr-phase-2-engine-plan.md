---
tags:
  - '#plan'
  - '#m210-irnr-phase-2-engine'
date: '2026-05-27'
modified: '2026-07-17'
tier: L3
related:
  - '[[2026-05-27-m210-irnr-full-engine-adr]]'
  - '[[2026-05-27-source-jurisdiction-axis-adr]]'
  - '[[2026-05-28-source-jurisdiction-axis-research]]'
  - '[[2026-07-10-m210-irnr-phase-2-engine-adr]]'
  - '[[2026-06-04-m210-irnr-phase-2-engine-research]]'
  - '[[2026-07-09-m210-irnr-phase-2-engine-adr]]'
---

# `m210-irnr-phase-2-engine` `M210 IRNR Phase 2 engine - full diseno-de-registro + Convenios roster + remaining tipo-de-renta variants` plan

## Wave `W01` - diseno-de-registro and Convenios roster

Land the M210 Phase 2 engine as the four independently-landable slices decided by the 2026-07-09-m210-irnr-phase-2-engine ADR, ordered by grounding availability. Slices A and B are bundled-groundable and executable now (official tipo-de-renta code axis; agrupacion anual period token, plazo windows, and grouping-validity predicates). Slices C and D are fetch-gated (Slice C on the official complete casilla enumeration; Slice D on per-treaty BOE convenio texts). Slice E (a 2027 revision under Orden HAC/623/2026 for the dividend-refund content change) is DEFERRED until the 2027 filing year approaches; it carries no blocker beyond calendar and folds its 2026 domiciliacion-plazo update into the Slice B deadline windows when authored. Authorising chain: 2026-07-09-m210-irnr-phase-2-engine-adr (slice decomposition + grounding map) plus the Phase 1 m210-irnr-full-engine-adr deferral.

### Phase `W01.P01` - Slice A: official tipo-de-renta code axis (bundled-groundable now)

Author the official M210 tipo-de-renta numeric code list as declared registry data on the 2025 revision, with a registry-authored code-to-`TipoRentaIrnr` projection and a build-time parity gate, and surface the code as a typed CLI Choice. One layout, code-keyed branches (ADR O2/O4); the conceptual `TipoRentaIrnr` enum stays the rate key.

- [x] `W01.P01.S01` - author the official M210 tipo-de-renta code list (01, 02, 27, 28, 29, 33, 35, ...) as declared registry data on the 2025 revision, each code row citing its bundled Orden EHA/3316/2010 and AEAT M210 instructions grounding; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters`.
- [x] `W01.P01.S02` - author the code-to-`TipoRentaIrnr` projection plus a registry-build parity gate that refuses at build any declared code with no mapping and any unmapped code; `src/aeat/core/_irnr.py`.
- [x] `W01.P01.S03` - declare the official tipo-de-renta code as a typed Typer Choice at the M210 CLI boundary and add its locale keys across en/es/ca/hu through the locale CLI; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W01.P02` - Slice B: agrupacion anual (bundled-groundable now)

Model agrupacion anual as period/deadline/predicate machinery, not a new aggregation mechanism (ADR O8): the period token `0A`, the Orden HAC/56/2024 plazo windows, and grouping-validity verification predicates over the declared rows, all grounded in the bundled Articulo cuarto text.

- [x] `W01.P02.S04` - add the M210 period token `0A` (agrupacion anual) to the canonical period grammar scoped to M210, resolved through the single `Period.contains` boundary authority; `src/aeat/domain/period.py`.
- [x] `W01.P02.S05` - declare the M210 plazo windows as REGISTRY deadline_windows TOML (grounded in the bundled CONSOLIDATED Orden EHA/3316/2010 art 5, in vigor 24/06/2026 - amended by HAC/56/2024 art 4.2 + HAC/623/2026 art 1.2), NOT hand-coded in the read-only _plazo.py resolver. CURRENT LAW (supersedes the stale HAC/56/2024 January wording the earlier spec carried): a-ingresar general = 20 primeros dias de abril/julio/octubre/enero por el trimestre natural anterior (period 1T-4T); `arrendamiento a-ingresar = 20 primeros dias de ABRIL del ano siguiente; cuota cero = 1-20 enero; a devolver = desde el 1 de febrero (4 anos); imputadas tipo 02 = presentacion todo el ano natural siguiente (1 enero-31 diciembre; la domiciliacion es 1 abril-23 diciembre). Only the a-ingresar-general quarterly (1T-4T) is a clean (modelo,period) window and is built now; the resultado/tipo-dependent annual plazos are DEFERRED to a resultado/tipo-keyed deadline ADR addendum (a period token cannot express a computed resultado or tipo). period_selector widen (1T-4T) also deferred - pinned EVENT-N by test_modelo_210_registry.py:110; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/deadline_windows/ + src/aeat/_data/registry/aeat/legal/irnr.toml + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/application_links/`.
- [x] `W01.P02.S06` - Implement the accepted M210 grouped-renta detail-row contract and registry row-set verification for agrupacion 0A, including the code-35 payer exception and no-offset rule; `src/aeat/domain/modelos + src/aeat/application/modelo`.

### Phase `W01.P03` - Slice C: full casilla schema (fetch-gated)

FETCH-GATED on NEEDS-FETCH 1 (the official complete M210 field enumeration): the AEAT Sede "Disenos de registro - modelo 210" document for the current campaign and/or the official M210 form specimen PDF from the Sede M210 procedure page. The "~80 casillas" figure is unverified and MUST be re-derived from the fetched document; no casilla beyond the instructions-groundable subset may be authored until the layout authority is bundled.

- [x] `W01.P03.S07` - FETCH-GATED (fetch: AEAT Sede "Disenos de registro - modelo 210" or the official M210 Sede form specimen) - fetch and bundle the official complete M210 field enumeration as a `layout_authority` corpus source; `src/aeat/_data/corpus/normatives/html`.
- [x] `W01.P03.S08` - author the complete M210 casilla set on the 2025 revision with completeness manifest, extraction-profile targets, and export parity, with casilla count and numbering taken from the fetched layout authority; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas`.

### Phase `W01.P04` - Slice D: Convenios roster tranche 1 (fetch-gated)

FETCH-GATED on NEEDS-FETCH 2 (per-treaty BOE consolidated convenio text). Demand-driven per-treaty enrolment (ADR O6): tranche 1 proposes FR, PT, US, NL, BE by non-resident filer volume; each treaty names its exact BOE ids at fetch time and ships corpus + legal entries + one `treaties/es-XX.toml` + a continuity parity test. Subsequent tranches enrol without framework change.

- [x] `W01.P04.S09` - FETCH-GATED (fetch: per-treaty BOE consolidated convenio texts for FR/PT/US/NL/BE) - author tranche-1 Convenio corpus, `legal/irnr.toml` entries, and `treaties/es-XX.toml` rows keyed by `TipoRentaIrnr` with typed `ConvenioOverrideKind`, pinned by continuity parity tests; `src/aeat/_data/registry/aeat/treaties`.

## Wave `W02` - source_jurisdiction per-row aggregation gating

Defence-in-depth layer for the source_jurisdiction axis that lands once both the M210 IRNR aggregation engine (this plan W01 + the cross-domain-continuity #256 closure) and the Beckham M151 aggregation engine (currently a Path-B refusal stub from cross-domain-continuity-plan task #161 / S185) are authored. The cross-domain-continuity source_jurisdiction axis (S381 through S386) already gates at the CLI create boundary with profile-conditional default and refusal; this wave layers per-row aggregation-time enforcement at the modelo engines themselves. Tracked as task #62 (deferred S385b) in the cross-domain-continuity follow-up queue. Blocker chain: this plan W01 must land first (or the cross-domain-continuity #256 IRNR engine equivalent, whichever ships earlier) AND the Beckham M151 aggregation engine must replace its Path-B refusal stub. Authorising chain: source-jurisdiction-axis-adr (Consequences section flags S385b as deferred) plus m210-irnr-full-engine-adr.

### Phase `W02.P05` - M210 IRNR base imponible scope filter

Project explicitly M210-classified, Spanish-source transaction rows through one registry-owned gross-income binding; surface foreign, unresolved, and incomplete rows as typed provenance-bearing issues before aggregation.

- [x] `W02.P05.S10` - Add the accepted M210 IRNR ledger binding source and registry selector for the gross-income target, with exclusive source ownership; `src/aeat/core/aggregation.py + src/aeat/_data/registry/aeat/modelos/210`.
- [x] `W02.P05.S11` - Implement explicit persisted M210 transaction classification plus its operator write surface, runtime tipo-renta source context, Spanish-source classifier, and resolver with typed foreign, unresolved, and incomplete-classification issues; `src/aeat/domain/transactions + src/aeat/entrypoints/cli + src/aeat/application/modelo + src/aeat/application/aggregation`.
- [x] `W02.P05.S12` - Add secure-store behavioural tests proving ES-only M210 aggregation, retained provenance, and source-jurisdiction/classification mutation outcomes; `src/aeat/application/aggregation/tests`.

### Phase `W02.P06` - Beckham M151 IRPF base segregation gate

Apply the LIRPF Art 93.5 segregation rule at the M151 aggregation surface: the Beckham regime taxes Spanish-source income at the flat IRNR rate while excluding foreign-source income from the IRPF base entirely. The CLI create boundary already refuses Beckham profiles that omit `--source-jurisdiction` (S384 resolver), so every row reaching the engine carries an explicit declaration. The aggregation gate splits the catalogue into two cohorts: `"ES"` rows feed the Beckham-track flat-rate computation; non-ES rows are emitted as `BECKHAM_FOREIGN_SOURCE_SEGREGATED` provenance entries that carry through the export pipeline for audit but do NOT contribute to the IRPF base.

- [x] `W02.P06.S13` - add the `source_jurisdiction` provenance pass-through on the M151 observation model; `src/aeat/application/aggregation`.
- [x] `W02.P06.S14` - add the per-row segregation gate in the M151 classifier so a row with `source_jurisdiction != "ES"` produces a `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue rather than a base observation, anchored on LIRPF Art 93.5; `src/aeat/application/aggregation`.
- [x] `W02.P06.S15` - add the anti-tautology test proving the Beckham IRPF base sums only the ES row, the DE row is emitted as a segregated issue with its jurisdiction preserved, and a gate-bypass mutant inflates the IRPF base by the DE row; `src/aeat/application/aggregation`.

### Phase `W02.P07` - predicate-shape decision and registry surface (architect call)

The cross-domain-continuity decomposition lands the S378 `implies_nonzero` operator as the closest existing predicate shape for per-row regulatory gating. The W02.P01 and W02.P02 filters above are CLASSIFIER-level filters (typed issues + base-sum exclusion), not registry-predicate-level verifiers. A predicate-level surface is the alternative shape: a registry-authored predicate such as `source_jurisdiction_must_equal_es_for_modelo(["m210"])` evaluated at the verification phase, surfacing a finding rather than gating the aggregation. The architect-2 call is whether the W02 wave is classifier-based (preferred by this draft) or predicate-based (operator-author-driven, more flexible but adds a new predicate name to `KNOWN_VERIFICATION_PREDICATE_OPERATORS` and a new regex/branch to `_evaluate_predicate_expression`).

- [x] `W02.P07.S16` - architect-2 selects classifier-based vs predicate-based shape, determining the S10/S11 and S13/S14 sites (if predicate-based, author a new operator following the S376/S377/S378 pattern, otherwise close as a no-op affirming the classifier-based Steps); `src/aeat/application/modelo/_verification_predicates.py`.

### Phase `W02.P08` - locale strings for the new issue kinds

Two new issue-reason locale keys, populated via `python -m aeat.locales scaffold` + per-locale `set` per the cross-domain-continuity S383b / S384b pattern. Refusal/issue messages must route through `tr()` per G3; never hand-edit yml structure.

- [x] `W02.P08.S17` - Localize the accepted M210 source-ingestion issue reasons through the locale CLI and route calculate-time diagnostics through the canonical translation surface; `src/aeat/locales + src/aeat/application/aggregation`.

### Phase `W02.P09` - cross-domain-continuity follow-up close

Once W02.P01 through W02.P04 land, close cross-domain-continuity task #62 (deferred S385b) and update the source-jurisdiction-axis-adr Consequences section to record the deferral closure with the W02 commit SHAs.

- [x] `W02.P09.S18` - Close cross-domain task #62 and update the source-jurisdiction ADR consequences with the verified M210 implementation commit SHAs; `.vault/adr/2026-05-27-source-jurisdiction-axis-adr.md`.
