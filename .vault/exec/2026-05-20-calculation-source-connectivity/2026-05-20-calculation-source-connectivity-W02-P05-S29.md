---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S29'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
  - "[[2026-07-04-counterpart-source-provider-adr]]"
---

# Adjudicate counterpart source provider against accepted 2026-07-04-counterpart-source-provider-adr (Option D): repository-backed provider in the counterpart family module, owned_sources narrowed to the two reserved kinds, RESERVED and non-enrolled until the first M347 declaring binding co-lands enrollment plus the S21 correctness gate

## Scope

- `src/aeat/application/aggregation/_counterpart.py`

## Description

- Ground the accepted `2026-07-04-counterpart-source-provider-adr` (Option D) against HEAD before acting; supersede the stale `S29` framing that named a non-existent `_registry_provider.py`.
- Confirm the pre-enrollment slice already landed at HEAD (operator commit `720d05529d`): `CounterpartAggregationSourceResolver.owned_sources` narrowed to exactly `ledger_transaction` and `purchase_invoice_evidence`, and the `InvoiceCatalogueSourceResolver` exclusive claim on `payable_invoice` / `collectible_invoice` is no longer contended.
- Verify the counterpart, application-mesh-parity, and missing-sources gates are green (35 passed): `owned_sources` equals the two reserved kinds, the resolver does not claim the invoice-owned M349 bindings, it stays silent when no counterpart binding is declared, and the disposition registry classifies both kinds `RESERVED` (not enrolled, not deferred).
- Correct the `S29` plan-row action and scope through the plan CLI: replace the `_registry_provider.py` enrollment framing with the Option D adjudication scoped to the counterpart family module `_counterpart.py`.
- Close plan step `W02.P05.S29` against the ADR.

## Outcome

- `W02.P05.S29` is adjudicated and closed against Option D. The pre-enrollment slice the ADR names (narrow `owned_sources`, resolve the invoice-catalogue collision, keep the counterpart kinds `RESERVED` and non-enrolled) is present and gate-green at HEAD, so no production code change was required this pass. The step is satisfied by the accepted design, per the ADR Consequences, not by authoring `_registry_provider.py`.

## Notes

- Deferred to co-land in ONE commit with the first M347 declaring binding (M347 declares zero bindings today): the repository-backed projection (bucket ledger plus encrypted purchase-invoice evidence into `CounterpartObservation` rows), enrollment of `CounterpartAggregationSourceResolver` in `merge_source_resolutions`, the S21-shape exact-equality correctness gate (live-mesh resolution equals prior `aggregate_counterpart_347` / `aggregate_counterpart_349` output on a 347 and a 349 fixture) plus the `M347_THRESHOLD_EUR` declaration-floor behaviour, and the fail-closed shape (empty-store advisory, storage-degradation raise, `deterministic_lock` override tier).
- Building the projection this pass was rejected as not honestly buildable: with no declaring binding the ledger-to-observation mapping is ungrounded (it would fabricate semantics with no registry binding or AEAT oracle to verify against), and a built-but-unenrolled resolver is a dormant resolver — both barred, and both contradict the ADR's own "registry binding build-out first, provider enrollment co-landing, no interim half-live state" sequencing.
- Binding-resolver `S20` / `S21` remain deferred on the same M347 dependency; they inherit their gate shape from this ADR.
- No optional regression guard was added: the mesh-parity and counterpart suites already pin `owned_sources`, the collision, and the `RESERVED` / non-enrolled disposition, so an additional test would be near-duplicative.
