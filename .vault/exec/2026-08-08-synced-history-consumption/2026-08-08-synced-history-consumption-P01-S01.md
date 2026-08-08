---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:cf981dde87bbb2f6fa5f86157cdf3994c4a1bbc27d128049250048e4ec732aed'
step_id: 'S01'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Census every calculation input channel that could have consumed a pulled AEAT filing fact

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/aggregation`
- `src/cadrumo/domain/calculations/registry`

## Description

- Load the registry through `bundled_authority()` and enumerate every compiled
  `ModeloRevision`'s bindings, relations and dependency classifications, so the
  denominator comes from the loaded snapshot rather than a directory listing.
- Read each binding's `source` field and partition the 1253 bindings by source
  kind before classifying any absence, keeping `profile`, ledger, invoice and
  deferred kinds out of the pulled-filing subset.
- Measure the pull's per-modelo support boundary from the same snapshot, since
  `_filed_capture_unsupported_reason` decides it on a registry-declared
  `live_cross_references` entry rather than a hardcoded list.
- Join that boundary against each carry channel's source modelo to split
  reaches-today from structurally-excluded.
- Trace the pull's write path and the carries' read path to establish whether
  provenance gates the consumption.
- Persist the census as a committed reference stating its denominator.

## Outcome

The census is committed as the census reference. Denominator: 73 modelos, 90
revisions, 1253 bindings over 24 source kinds, 74 relations, 53 dependency
classifications.

Only 81 bindings of the 1253 (6.5 %) draw a value from a prior return, split
`previous_filing` 17, `relation_prefill` 62, `iva_compensation_annual_partition`
2. Of those 81, 72 have a pull-reachable source modelo and 9 are structurally
excluded, all on Sociedades: 5 on modelo 200 and 4 on modelo 202, neither of
which declares a filed-declarations read surface on any revision. 23 of 73
modelos declare that surface. The 53 dependency classifications are a
reconciliation gate rather than a value input and are reported as such.

The step also overturns the premise it was dispatched to quantify. The research
document holds that the pulled filing record has exactly one consumer in the
calculation engine and that every other previous-filing carry reads a store the
pull does not write. Both halves are wrong.
`persist_filed_calculation_observation` writes EVERY pulled modelo's active filed
observation into `CalculationObservationRepository` with
`ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE`, reached by all three capture
routes through `finalize_filed_capture`; the Modelo 303 branch inside it is an
additional write to `IvaCompensationHistoryRepository`, not the only write. And
`resolve_bindings_from_local_store` and `resolve_relations_from_local_store` load
that same repository by key with NO provenance filter — `_LOCAL_FILING_PROVENANCE`
is a model field default, not a predicate, and `_source_kind_for_binding` reports
provenance rather than gating on it. Both resolvers are enrolled on the live
calculate mesh.

The single-consumer reading is true of `IvaCompensationHistoryRepository`
specifically and of `persist_iva_compensation_history_observations_strict`, which
does raise for any modelo other than 303. It is not true of the calculation
engine's consumption of pulled facts.

## Verification

Three read-only probes over the loaded authority, run from the repository root
against the bundled registry (no registry was installed into the shared path):

    uv run --no-sync python <scratch>/census_probe.py
    modelos: 73, revisions: 90, bindings_total: 1253,
    relations_total: 74, dependency_classifications_total: 53

    uv run --no-sync python <scratch>/reach_probe.py
    modelos with a filed-declarations read surface on >=1 revision: 23
    relations: {'source_pullable': 61, 'source_not_pullable': 13}
    previous_filing bindings: {'source_pullable': 17}

    uv run --no-sync python <scratch>/slot_probe.py
    {'fed_by_pullable_source': 53, 'all_feeders_not_pullable': 9}

The per-source-kind partition sums to the 1253 total, which is the arithmetic
check that no binding was dropped or double-counted between the subset and the
excluded remainder. The `relation_prefill` split was measured rather than
hand-derived from the relation counts, and the probe reported zero orphan slots,
so every one of the 62 slots is accounted by a feeder relation.

No pytest lane was run: this step produced no production code and no test.

## Notes

Reachability here is a JOIN of a measured write against a measured unfiltered
read. No run was executed in which a pulled observation was persisted and a
subsequent calculation was then observed to consume it, so "reaches today" is an
inference from two measurements rather than an end-to-end observation. That
execution is the next step's work and its outcome may narrow these verdicts. The
reference states this limitation in its own closing section rather than leaving it
to this record.

Three runtime conditions gate a reachable channel and none was exercised:
incomplete `extraction_coverage` refuses a whole filing's enrolment all-or-nothing;
an observed casilla that is not canonical for the resolved revision, or whose
registry grounding is incomplete, refuses; and the revision carry gate drops a
divergent or unreconfirmable revision stamp from the fold.

Nothing was committed beyond the census reference, and no production file was
touched. The plan's headline framing — that the census should report "the one
wired channel as one row out of that total" — could not be honoured as written,
because the measurement found more than one wired channel. The row is reported as
what it is instead.
