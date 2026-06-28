---
tags:
  - '#plan'
  - '#m210-irnr-phase-2-engine'
date: '2026-05-27'
modified: '2026-05-27'
tier: L3
related:
  - '[[2026-05-27-m210-irnr-full-engine-adr]]'
  - '[[2026-05-27-source-jurisdiction-axis-adr]]'
  - '[[2026-05-28-source-jurisdiction-axis-research]]'
  - '[[2026-06-04-m210-irnr-phase-2-engine-adr]]'
  - '[[2026-06-04-m210-irnr-phase-2-engine-research]]'
---


# `m210-irnr-phase-2-engine` `M210 IRNR Phase 2 engine - full diseno-de-registro + Convenios roster + remaining tipo-de-renta variants` plan

## Wave `W01` - diseno-de-registro and Convenios roster

Backfill the full M210 diseno de registro per AEAT Orden HAC/56/2024 across all tipo-de-renta variants (Arts 25.1.b pensiones, 25.2 rentas inmobiliarias, 25.3 ganancias patrimoniales, 25.5 pagos a cuenta), populate the m210-convenio-rates parameter for the full ~92 country Convenios Espana roster, and add agrupacion-anual presentation support per the Phase 1 ADR D7 out-of-scope list. Authorising chain: m210-irnr-full-engine-adr Phase 2 deferral plus cross-domain-continuity-adr epic.

## Wave `W02` - source_jurisdiction per-row aggregation gating

Defence-in-depth layer for the source_jurisdiction axis that lands once both the M210 IRNR aggregation engine (this plan W01 + the cross-domain-continuity #256 closure) and the Beckham M151 aggregation engine (currently a Path-B refusal stub from cross-domain-continuity-plan task #161 / S185) are authored. The cross-domain-continuity source_jurisdiction axis (S381 through S386) already gates at the CLI create boundary with profile-conditional default and refusal; this wave layers per-row aggregation-time enforcement at the modelo engines themselves. Tracked as task #62 (deferred S385b) in the cross-domain-continuity follow-up queue. Blocker chain: this plan W01 must land first (or the cross-domain-continuity #256 IRNR engine equivalent, whichever ships earlier) AND the Beckham M151 aggregation engine must replace its Path-B refusal stub. Authorising chain: source-jurisdiction-axis-adr (Consequences section flags S385b as deferred) plus m210-irnr-full-engine-adr.

### Phase `W02.P01` - M210 IRNR base imponible scope filter

Apply the TRLIRNR Art 25.1 base-scope rule at the M210 aggregation surface: only rows whose source_jurisdiction is `"ES"` enter the IRNR base imponible. Foreign-source rows on a non-resident profile are a category error at the CLI boundary (refused by S384's `_resolve_source_jurisdiction`) but the aggregation engine must still defend the contract for catalogues imported before the CLI gate landed, for catalogues set up through a future API surface, and for the rare legitimate case where a non-resident operator has staged a foreign-source row as informational provenance (audit trail, never as IRNR base). The filter is provenance-respecting: foreign-source rows are NOT silently dropped from the catalogue read; they are excluded from the base sum with a typed `IrnrAggregationIssueReason.FOREIGN_SOURCE_OUT_OF_SCOPE` finding that carries the transaction id and the original jurisdiction code so the operator sees what was excluded and why.

- [ ] `W02.P01.S01` - add `source_jurisdiction: str | None` provenance pass-through to the M210 aggregation observation model (mirror the cross-domain-continuity S385 / W12.P65.S385 pattern on `RentaIncomeObservation`); the field carries the per-row jurisdiction from `Transaction.source_jurisdiction` for downstream audit. `src/aeat/application/aggregation/...irnr...` (path TBC by the engine implementor under this plan W01).
- [ ] `W02.P01.S02` - add the per-row base-scope filter in the M210 classifier: when `source_jurisdiction != "ES"` and the operator profile is `fiscal_residency == NON_RESIDENT_IRNR`, classify the row as a `FOREIGN_SOURCE_OUT_OF_SCOPE` issue rather than emitting a base-imponible observation. Anchor: TRLIRNR Art 25.1 (base imponible scope is Spanish-source income only). `src/aeat/application/aggregation/...irnr...`.
- [ ] `W02.P01.S03` - real-engine anti-tautology test: build a non-resident catalogue with one ES-source row plus one FR-source row; assert (a) the IRNR base sum equals only the ES amount, (b) a `FOREIGN_SOURCE_OUT_OF_SCOPE` issue is emitted for the FR row with the transaction id and `"FR"` jurisdiction recorded, (c) a mutant where the filter is removed would silently double-count the FR row into the IRNR base (strict-inequality witness). `src/aeat/application/aggregation/test_irnr_aggregation.py` (or sibling).

### Phase `W02.P02` - Beckham M151 IRPF base segregation gate

Apply the LIRPF Art 93.5 segregation rule at the M151 aggregation surface: the Beckham regime taxes Spanish-source income at the flat IRNR rate while excluding foreign-source income from the IRPF base entirely. The CLI create boundary already refuses Beckham profiles that omit `--source-jurisdiction` (S384 resolver), so every row reaching the engine carries an explicit declaration. The aggregation gate splits the catalogue into two cohorts: `"ES"` rows feed the Beckham-track flat-rate computation; non-ES rows are emitted as `BECKHAM_FOREIGN_SOURCE_SEGREGATED` provenance entries that carry through the export pipeline for audit but do NOT contribute to the IRPF base.

- [ ] `W02.P02.S01` - add the same `source_jurisdiction` provenance pass-through on the M151 observation model.
- [ ] `W02.P02.S02` - add the per-row segregation gate in the M151 classifier: rows where `source_jurisdiction != "ES"` produce a `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue rather than a base observation. Anchor: LIRPF Art 93.5 (Beckham segregation - foreign-source income is outside the IRPF base for impatriados).
- [ ] `W02.P02.S03` - anti-tautology test: build a Beckham catalogue with one ES-source row plus one DE-source row; assert (a) IRPF base sum is only the ES amount, (b) the DE row is emitted as a segregated issue with its jurisdiction preserved, (c) the mutant case where the gate is bypassed would inflate the IRPF base by the DE row's amount.

### Phase `W02.P03` - predicate-shape decision and registry surface (architect call)

The cross-domain-continuity decomposition lands the S378 `implies_nonzero` operator as the closest existing predicate shape for per-row regulatory gating. The W02.P01 and W02.P02 filters above are CLASSIFIER-level filters (typed issues + base-sum exclusion), not registry-predicate-level verifiers. A predicate-level surface is the alternative shape: a registry-authored predicate such as `source_jurisdiction_must_equal_es_for_modelo(["m210"])` evaluated at the verification phase, surfacing a finding rather than gating the aggregation. The architect-2 call is whether the W02 wave is classifier-based (preferred by this draft) or predicate-based (operator-author-driven, more flexible but adds a new predicate name to `KNOWN_VERIFICATION_PREDICATE_OPERATORS` and a new regex/branch to `_evaluate_predicate_expression`).

- [ ] `W02.P03.S01` - architect-2 reviews and selects classifier-based vs predicate-based shape; the chosen shape determines the S01/S02 sites for W02.P01 and W02.P02. If predicate-based, author a new operator following the S376/S377/S378 pattern (register on `KNOWN_VERIFICATION_PREDICATE_OPERATORS`, runtime branch in `_evaluate_predicate_expression`, anti-tautology test suite). If classifier-based, the W02.P01/W02.P02 Steps above are authoritative and this Step is a no-op closure.

### Phase `W02.P04` - locale strings for the new issue kinds

Two new issue-reason locale keys, populated via `python -m aeat.locales scaffold` + per-locale `set` per the cross-domain-continuity S383b / S384b pattern. Refusal/issue messages must route through `tr()` per G3; never hand-edit yml structure.

- [ ] `W02.P04.S01` - scaffold and populate `aggregation.irnr.issues.foreign_source_out_of_scope_label` and `aggregation.beckham.issues.foreign_source_segregated_label` across `en` / `es` / `ca` / `hu`.

### Phase `W02.P05` - cross-domain-continuity follow-up close

Once W02.P01 through W02.P04 land, close cross-domain-continuity task #62 (deferred S385b) and update the source-jurisdiction-axis-adr Consequences section to record the deferral closure with the W02 commit SHAs.

- [ ] `W02.P05.S01` - mark task #62 completed; append a "Deferral resolved" subsection to the source-jurisdiction-axis-adr Consequences section listing the W02.P01 + W02.P02 commit SHAs.
