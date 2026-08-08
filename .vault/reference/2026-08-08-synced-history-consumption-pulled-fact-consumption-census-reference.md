---
tags:
  - '#reference'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8a4c52c603b4e08352bc6726f73e8b12531eeec591d2caf69c59721bbf89218c'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-research]]"
---

# `synced-history-consumption` reference: `which pulled AEAT facts reach the calculation engine`

## Summary

Every figure below is derived from the LOADED registry material through
`bundled_authority()` in `src/cadrumo/domain/calculations/registry/_authority.py`,
by iterating each `ModeloDefinition.revisions` mapping and reading the compiled
`bindings`, `relations` and `dependency_classifications` off each
`ModeloRevision`. No count comes from a directory listing or a file-shape glob,
so directory-mode fragments are included by construction.

## The denominator

The registry compiles to 73 modelos across 90 revisions, carrying 1253 data
bindings drawing on 24 distinct source kinds, 74 relations, and 53 cross-period
dependency classifications.

Bindings by source kind, summing to 1253:

| source kind | bindings |
| --- | --- |
| `manual_input` | 783 |
| `profile` | 108 |
| `ledger_iva_aggregation` | 138 |
| `ledger_renta_gastos_estimacion_directa_aggregation` | 28 |
| `ledger_renta_income_aggregation` | 10 |
| `ledger_oss_aggregation` | 5 |
| `ledger_impatriado_income_aggregation` | 2 |
| `ledger_irnr_income_aggregation` | 1 |
| `ledger_renta_gastos_pago_fraccionado_aggregation` | 1 |
| `collectible_invoice` | 19 |
| `payable_invoice` | 17 |
| `retenciones_aggregation` | 14 |
| `withholding` | 14 |
| `foreign_asset` | 6 |
| `atribucion_member` | 4 |
| `prorrata_regularizacion` | 3 |
| `bienes_inversion_regularizacion` | 3 |
| `related_party_operation` | 6 |
| `refund_operation` | 5 |
| `donativo_donor` | 5 |
| `relation_prefill` | 62 |
| `previous_filing` | 17 |
| `iva_compensation_annual_partition` | 2 |

Relations by kind: 46 `cross_model_output`, 20 `annual_summary`, 8
`previous_period`. Dependency classifications by treatment: 32
`direct_annual_settlement`, 17 `factual_evidence`, 4 `non_dependency`.

## The subset a pulled filing could ever feed

A pulled AEAT filing is a record of casilla values a prior return declared. Only
three source kinds draw a value from a prior return: `previous_filing` (17),
`relation_prefill` (62) and `iva_compensation_annual_partition` (2). That is 81
bindings, 6.5 % of the 1253.

The remaining 1172 are structurally excluded because their substrate is not a
prior filing at all, and their absence on a freshly-onboarded profile is not a
synced-history defect:

- 783 `manual_input` are operator input by design.
- 108 `profile` read declared censal and profile facts, not filings. A `profile`
  binding missing from a filing sweep is not a silent zero of this class.
- 185 `ledger_*` read the bucket transaction ledger.
- 36 invoice bindings (`collectible_invoice`, `payable_invoice`) read the invoice
  substrate.
- 28 read dedicated operator stores (`retenciones_aggregation`, `withholding`).
- 16 are the explicitly deferred kinds (`related_party_operation`,
  `refund_operation`, `donativo_donor`), which emit a standing advisory rather
  than a silent blank and are therefore accounted, not a gap.
- 16 are other non-filing substrates (`foreign_asset`, `atribucion_member`,
  `prorrata_regularizacion`, `bienes_inversion_regularizacion`).

## The pull-support boundary is registry-declared

Whether a modelo can be pulled from the AEAT declarations register is decided by
`_filed_capture_unsupported_reason` in
`src/cadrumo/application/live/_filed_data_capture.py`, which requires the
revision to carry a `live_cross_references` entry whose `surface` is
`authenticated_read_surface` and whose id ends `filed-declarations-read`. That
makes the boundary measurable from the snapshot rather than inferred.

23 of the 73 modelos declare that surface on at least one revision: 100, 111,
115, 123, 130, 131, 180, 184, 190, 193, 232, 303, 308, 309, 322, 347, 349, 353,
360, 369, 390, 720, 840. The other 50 do not, and Sociedades is the consequential
absence: neither 200 nor 202 is pullable.

## Per-channel reachability

Reachability joins the pull's write path against each channel's read path.

**Write path.** `finalize_filed_capture` in
`src/cadrumo/application/live/_filed_capture_finalizer.py` calls
`persist_filed_calculation_observation`, which writes the registry-grounded
observation into `CalculationObservationRepository` with
`source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE`. It is not scoped to
one modelo: every active (ALTA) filed observation of every pulled modelo is
written. All three capture routes — single, bulk and source — reach it, and the
CLI verb `app.live.filed.pull` reports the resulting
`calculation_observation_count`.

**Read path.** `resolve_bindings_from_local_store`
(`src/cadrumo/application/calculations/_binding_prefill.py`) and
`resolve_relations_from_local_store`
(`src/cadrumo/application/calculations/_relation_prefill.py`) both load from that
same repository by `(modelo, filing_year, period)` key. Neither applies a
provenance filter. `_gathered_observation(..., source_kind=payload.source_kind)`
reads the persisted provenance and REPORTS it; `_source_kind_for_binding`
likewise reports rather than gates. `_LOCAL_FILING_PROVENANCE` is a default value
on the `PrefilledBinding` and `LocalIvaCompensationRecurrence` model fields, not a
predicate. Both resolvers are enrolled on the live calculate mesh in
`src/cadrumo/application/modelo/_calculation_actions.py`.

The resulting channel table:

| channel | count | verdict | reason |
| --- | --- | --- | --- |
| `previous_filing` bindings | 17 | reaches today | every one resolves against a source modelo that declares the filed-declarations read surface: 100, 130, 131, 303, 322, 720 |
| `relation_prefill` slots fed by a pullable source | 53 | reaches today | feeder relations name 100, 111, 115, 123, 130, 131, 184, 190, 193, 303 |
| `relation_prefill` slots whose every feeder is unpullable | 9 | structurally excluded | 5 on modelo 200 and 4 on modelo 202; feeders are 200 and 202, neither of which declares the read surface |
| `iva_compensation_annual_partition` | 2 | reaches today | modelo 390 partition of filed 303 history, and 303 is pullable |
| relations, source pullable | 61 of 74 | reaches today | materialise into the 53 slots above |
| relations, source unpullable | 13 of 74 | structurally excluded | all on 200 and 202 |
| dependency classifications | 53 | reconciliation gate, not an input | consumed by the cross-period clean-state evaluation, which decides readiness rather than supplying a value |

So of the 81 bindings a pulled filing could feed, 72 have a pull-reachable
source and 9 are structurally excluded by the register's modelo coverage.

## The research document's premise is wrong on mechanism

The research document states that the pulled filing record has exactly one
consumer in the calculation engine, the Modelo 303 IVA compensación history, and
that every other previous-filing carry reads a store the pull does not write.
Measurement contradicts both halves.

`persist_filed_calculation_observation` writes every pulled modelo into the one
store the general carries read; the M303 branch inside it is an ADDITIONAL write
to `IvaCompensationHistoryRepository`, not the only write. And the general carry
readers apply no provenance filter, so an `aeat_sede_justificante` observation is
consumed on the same path an `app_filing` one is. The single-consumer reading
holds only for `IvaCompensationHistoryRepository` specifically; it does not
describe the calculation engine's consumption of pulled facts.

`persist_iva_compensation_history_observations_strict` IS modelo-303-only and
raises for any other modelo, which is the likely origin of the mistaken reading.

## What this census does not establish

It does not establish that a pulled value reaches a computed casilla end to end.
Reachability here is a join of a measured write and a measured unfiltered read;
no run was executed in which a pulled observation was persisted and a subsequent
calculation was observed to consume it. That execution is the next step's work,
and its outcome may narrow these verdicts.

Three conditions gate a reachable channel at runtime and none of them was
exercised:

- `registry_observation_from_filed_declaration` raises when
  `extraction_coverage` is absent or below 1.0 for any artefact kind, so a
  partially-extracted declaration enrols nothing. Enrolment is all-or-nothing per
  filing.
- The same function raises when an observed casilla is not a canonical casilla id
  of the resolved revision, or when that casilla's registry `legal_refs` or
  `source_refs` are incomplete. Non-numeric casillas are skipped rather than
  fatal, and enumerated for the operator.
- The revision carry gate re-confirms each observation's `stamped_revision_id`
  against the law-determined revision and drops a divergent or unreconfirmable
  stamp from the fold. Since `save_observation` stamps from the law-determined
  revision at capture time, a same-law read reconfirms; a later change to the
  revision that governs the source triple would refuse the carry.

It also does not establish whether any of these values SHOULD be consumed. That
is a decision, and the constraint that a pulled filing is evidence of what was
declared rather than an authorised input to a new computation stands untouched by
this measurement.
