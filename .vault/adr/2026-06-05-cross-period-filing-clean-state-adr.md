---
tags:
  - '#adr'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-cross-period-calculation-guards-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
  - '[[2026-06-05-cross-period-calculation-guards-research]]'
  - '[[2026-06-05-cross-period-calculation-guards-reference]]'
  - '[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-06-02-modelo-filing-ledger-snapshot-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---

# `cross-period-filing-clean-state` adr: `uniform filing-grade dependency proof for cross-period modelos` | (**status:** `accepted`)

## Problem Statement

Cross-period modelos derive current filing values from filings in other periods, years,
or group members. Modelo 390 is the visible annual example, but the registry and
calculation surfaces also include direct previous-filing bindings, registry relations,
prior-period carry-forward, prior-year baselines, annual rollups, and cross-member
aggregation.

The current architecture can calculate or prefill from available observations, but it
does not bind filing-grade calculation, verification, export, and filing to a uniform
proof that every upstream filing is present, current, verified or externally imported,
AEAT-attested, and reconciled against local values. Missing dependencies can remain
blank, manually supplied, or silently absent from coverage reports. That behavior is
acceptable for an explicit diagnostic preview, but not for a dependable tax filing
system.

## Considerations

The registry layer already describes many cross-period dependencies. Its strict
resolvers can reject incomplete direct dependency input once callers provide the
expected observation set. The application prefill layer is intentionally permissive:
`resolve_bindings_from_local_store` can skip missing previous-filing values, and
relation prefill can emit operator-manual blank values when local source observations
are absent.

Filing records carry stronger state than observation envelopes. `ModeloRecord` can
represent current versus superseded state and attach external AEAT evidence, while
`CalculationRevision` and `VerificationReport` represent local calculation and
verification state. `CalculationObservationRepository` is value-centric and stores
source kind and captured time, but it does not by itself prove current filing state,
external evidence, or reconciliation.

Existing ADRs already reject plausible-zero source synthesis, bind verified-complete
workflows to source traceability, require immutable ledger snapshots for filed
revisions, and define remote-evidence reconciliation for IVA compensation. This ADR
generalizes those duties to all cross-period filing dependencies.

## Constraints

The decision must not be Modelo 390 specific. The affected class includes every
registry-declared dependency whose value is derived from another filing period, filing
year, or member declaration.

The default previous-filing uniqueness guard remains load-bearing. Non-group
cross-period dependencies require exactly one current effective upstream filing.
Cross-member fan-in is only valid when the registry explicitly declares member-aware
aggregation and the complete expected member set is proven.

`source_kind` is not legal authority. It can help classify observations, but a
filing-grade proof must join observations to current filing records, filed or imported
calculation revisions, successful verification results, and official AEAT evidence
where available.

Manual operator values, blank fallback, unresolved bindings, storage degradation,
missing evidence, stale evidence, superseded filings, duplicate current candidates,
and local versus AEAT divergence cannot be treated as filing-grade values.

## Implementation

Introduce an application-layer cross-period clean-state proof service. The service
derives its requirement graph from the selected registry snapshot and the target
modelo filing context. It classifies each required upstream dependency as clean or
blocking by joining registry requirements, calculation observations, filing records,
calculation revisions, verification reports, imported external filing evidence, and
live AEAT capture artifacts.

For each required upstream filing, the proof must establish:

- the required `(modelo, filing year, period, member)` exists;
- the effective filing state is current, with exactly one current filing for
  non-group dependencies or a complete expected member set for group fan-in;
- local dependencies are backed by a current `ModeloRecord`, a filed
  `CalculationRevision`, a successful verification report, and observation values that
  match the filed revision values for the required casillas;
- AEAT-attested dependencies are backed by official evidence such as justificante,
  CSV/register evidence, or live filed-data capture;
- local and AEAT values are reconciled, and any divergence is represented as a typed
  blocking verdict until an explicit reconciliation decision is recorded.

Calculation may still offer an explicit non-filing diagnostic preview that shows
missing or unresolved cross-period values. Filing-grade calculation, verification,
export, readiness checks, and filing must refuse when the clean-state proof is absent
or blocking.

Lower-level prefill helpers may remain permissive preview mechanisms, but their
coverage reports cannot be treated as sufficient proof. The filing-grade boundary must
consume the clean-state proof service and return typed verification findings or export
errors instead of silently producing blank or operator-manual values.

## Rationale

The filing system must calculate cross-period modelos against the same filing values
that AEAT has received. Local calculations alone are insufficient when the downstream
modelo aggregates prior filings. AEAT evidence alone is also insufficient when it
cannot be reconciled to the local calculation history. The defensible state is the
intersection: complete registry-derived dependency coverage, current local filing
state, official external evidence, and reconciled values.

Keeping the proof at the application layer preserves registry purity and hexagonal
boundaries. The registry continues to define dependencies and strict value-resolution
rules; repositories continue to expose storage and evidence records through ports; the
application service composes those surfaces into a filing-grade verdict.

## Consequences

Cross-period modelos will fail closed at filing-grade boundaries when upstream filing
history is incomplete, stale, superseded, manually substituted, unverifiable, or
divergent. This is stricter than the current preview-friendly behavior and will
surface more blocking findings before users can verify or file annual, carry-forward,
prior-year, and group aggregate modelos.

The application will need a durable proof model that can explain missing requirements,
current-state conflicts, evidence gaps, verification gaps, and reconciliation
mismatches. Observation storage may need future schema expansion to persist stronger
evidence references and reconciliation fingerprints. Until that exists, source kind is
only a diagnostic hint and cannot replace joined filing/evidence records.

This decision creates a common enforcement point for Modelo 390, Modelo 303 continuity,
Modelo 200 and 202 prior-year or prior-period dependencies, informative annual
summaries, retention summaries, and Modelo 353 group aggregation. It also prevents
future models from bypassing the same rule by adding a new permissive source resolver.

## Codification candidates

- **Rule slug:** `cross-period-filing-clean-state`.
  **Rule:** Every filing-grade cross-period modelo dependency must be backed by a
  registry-derived clean-state proof covering current filing state, successful local
  verification or external import, official AEAT evidence, and reconciled values; manual
  or unresolved fallback is preview-only.
