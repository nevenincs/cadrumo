---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:62702df9a51d15e95433532c28b3f9a304b92c775db08d388f24a30d52da135f'
step_id: 'S15'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Prefix the ledger-aggregation-tier Observation carriers with a consistent domain prefix (IvaLedgerObservation, OssIossLedgerObservation, RetencionObservation, CounterpartObservation, CounterpartAggregationObservation, ForeignAssetIngestObservation, RentaDeductibleExpenseObservation, the detail-record family RelatedPartyOperationObservation / Modelo720RowObservation / AtributionMemberObservation / RefundOperationObservation, WithholdingObservation, InvoiceObservation), one atomic relocation commit per renamed carrier tagged relocation:<symbol>, each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit

## Scope

- `collect-only clean before each commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/application/aggregation/_retenciones.py`
- `src/aeat/application/aggregation/_counterpart.py`
- `src/aeat/domain/calculations/registry/_counterpart_bindings.py`
- `src/aeat/application/aggregation/_foreign_assets.py`
- `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `src/aeat/domain/calculations/registry/_withholding_bindings.py`
- `src/aeat/domain/calculations/registry/_invoice_bindings.py`

## Description

- Ground the ledger-aggregation tier via RAG then confirm every base `*Observation` carrier by grep: `IvaLedgerObservation`, `OssIossLedgerObservation`, `RetencionObservation`, `CounterpartObservation`, `CounterpartAggregationObservation`, `ForeignAssetIngestObservation`, `RentaDeductibleExpenseObservation`, `RelatedPartyOperationObservation`, `Modelo720RowObservation`, `AtributionMemberObservation`, `RefundOperationObservation`, `WithholdingObservation`, `InvoiceObservation`.
- Assert each carrier already leads with a domain-discriminating word and that no two `*Observation` carriers across the whole tree share an identical class name (deduplicate scan clean), so the prefix discipline is satisfied with no bare-stem hard collision to resolve.
- Confirm the two audit-flagged carriers (`RetencionObservation`, `CounterpartObservation`) are the load-bearing stem of their role-suffixed families the plan preserves (`RetencionObservationRepository`, `RetencionObservationEnvelopePayload`, `CounterpartObservationRequirement`); renaming the base carrier alone would de-sync that family, which S18 forbids.
- Confirm the sole residual old-name reference for those two carriers is the operator-facing locale help prose (`retencion_observation_help`, `counterpart_observation_help`) across all four catalogues, which currently carry non-authored peer WIP, so no grep-clean atomic rename is possible without clobbering peer work.

## Outcome

No new rename was required or possible for the ledger-aggregation tier. All thirteen carriers already carry a domain-discriminating prefix and no two carriers collide by class name, so the tier prefix discipline holds as-is. The two carriers a stricter reading might further prefix (`RetencionObservation`, `CounterpartObservation`) are correctly anchored to their plan-preserved role-suffixed families and their only would-be old-name residual lives in peer-WIP-locked operator locale help; further-prefixing them is out of the W03 internal-naming scope and structurally blocked. Verified no-shift: `pytest --collect-only -q` clean over the affected surfaces and the aggregation carrier test modules green (`test_retenciones.py`, `test_counterpart.py`, `test_retencion_observations_repository_roundtrip.py`).

## Notes

Deliberate no-op-rename closure, mirroring this plan's `S03` conditional assert. All target files were checked clean of peer WIP except the four locale catalogues (`ca.yml`, `en.yml`, `es.yml`, `hu.yml`), which hold non-authored WIP; abort-on-WIP was honored and none were touched. The sede/inbound peer relocation renames that satisfy the sibling `S16` tier landed earlier on this branch. No production code was modified in this Step.
