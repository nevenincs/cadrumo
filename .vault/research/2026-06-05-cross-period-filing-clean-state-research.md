---
tags:
  - '#research'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-06-02-modelo-filing-ledger-snapshot-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-05-26-cross-domain-continuity-audit]]'
  - '[[2026-04-12-modelo-303-390-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
---

# `cross-period-filing-clean-state` research: `uniform clean-state gate for cross-period modelo dependencies`

This research audits whether the current workspace already binds a filing-grade
state contract for modelos that consume prior filings, prior periods, prior
years, annual summaries, or cross-member filed observations. Modelo 390 is the
example that surfaced the issue, but the audited class is broader: every
registry `previous_filing` binding, registry relation, same-year period rollup,
prior-year baseline, prior-period carry-forward, and cross-member group
aggregation whose calculation result depends on filed history.

## Findings

No existing ADR fully binds the strong clean-state rule. The current vault
records bind adjacent pieces: source-mesh visibility, registry-backed
calculation truth, immutable ledger snapshots, local projection of live-read
captures, and conservative IVA wallet evidence. None states that a
cross-period modelo is filing-grade calculable only when each required upstream
filing is current, verified, filed, AEAT-attested, justificante-backed, and
reconciled against the local calculation that produced or imports it.

Current implementation supports cross-period dependency discovery and value
resolution, but it does not enforce that clean state uniformly:

- `src/aeat/application/calculations/_binding_prefill.py` resolves
  `previous_filing` bindings from `CalculationObservationRepository`.
  Its contract explicitly skips unavailable bindings and leaves strict
  enforcement to callers through coverage inspection.
- `src/aeat/application/calculations/_relation_prefill.py` resolves registry
  relations from prior filing observations. Missing or invalid relation
  sources become blank/operator-manual relation values instead of a hard
  filing-grade refusal.
- `src/aeat/application/calculations/_multi_year.py` documents that the
  multi-year resolver does not invent missing history, but returns shorter
  reports and leaves refusal, prompt, live fallback, or zero-fill decisions to
  callers.
- `src/aeat/application/calculations/_observations_repository.py` persists
  `RegistryModeloObservation`, `captured_at`, `source_kind`, and optional
  `member_nif`. It does not persist filing-record id, AEAT row status,
  justificante reference, captured artefact reference, reconciliation verdict,
  external-evidence kind, or an upstream verification report pointer.
- `src/aeat/domain/modelos/_filing_record.py` carries stronger filing-state
  concepts: current/superseded status, AEAT acceptance, and external evidence
  kinds for justificante PDF, CSV register, and live capture. The cross-period
  resolvers do not consult this catalogue.
- `src/aeat/application/live/__init__.py` can capture filed dependency sources
  through `capture_source_filed_data` and can promote AEAT filed observations
  into the calculation observation store with `source_kind =
  "aeat_sede_justificante"`. Promotion still stores only a calculation
  observation, not the full clean-state proof.
- `src/aeat/application/modelo/_actions.py` verifies required manual inputs,
  registry predicates, content integrity, ledger snapshot evidence, and IVA
  wallet reconciliation. It does not generally re-check that every
  cross-period source dependency is backed by a current filing record,
  reconciled justificante, AEAT live capture, and matching local calculation.
- `src/aeat/application/modelo/_export.py` allows export from verified-complete
  or filed revisions and checks ledger evidence parity, but it does not impose
  a separate upstream clean-state dependency gate.

The strict registry-side resolver exists but is not the end-to-end gate. The
domain previous-filing resolver can refuse missing, duplicate, or incomplete
observations once handed an expected observation set. The application-layer
prefill path gathers only available observations before invoking it; therefore
absence can be normalized into no prefill rather than a calculation-refusing
state.

The registry-declared affected class is already broad. Current committed
registry data includes `previous_filing` bindings or period-aligned relations
for Modelo 100, 130, 131, 180, 190, 193, 200, 202, 303, 353, and 390, with
additional prior-year or fidelity-style models in the calculation tests. This
confirms the ADR must not be 390-specific.

The clean-state rule has two distinct source categories:

- Local internal filings: a source observation can be trusted for
  filing-grade dependency resolution only if it is tied to a current
  `ModeloRecord`, whose calculation revision is `PRESENTADO`, was previously
  `VERIFICADO_COMPLETO`, has not been superseded, and whose filed values still
  match the persisted observation.
- AEAT-attested external filings: a source observation can be trusted only if
  it is tied to external evidence such as justificante PDF, CSV register, or
  live capture, carries enough artefact/reference metadata to audit the source,
  and has been reconciled against the relevant local calculation or imported
  as an external baseline with an explicit AEAT-accepted record.

The current state model has no single boundary object that can answer "is this
upstream filing clean for downstream calculation?" across both categories.
That absence is the core architectural gap.

## Recommendation

Write a binding ADR that classifies cross-period filing dependencies as
filing-grade only under a uniform clean-state contract.

Recommended decision:

Any calculation, verification, export, or filing-grade workflow for a modelo
that consumes prior filings through `previous_filing`, relations,
prior-period carry-forward, prior-year baseline, annual-summary rollup, or
cross-member filed observation must fail closed unless all required upstream
filing dependencies are complete and clean.

Clean means:

- The dependency graph is registry-derived from the selected `RegistrySnapshot`;
  callers cannot declare a smaller ad hoc source set.
- Every required `(modelo, filing_year, period, member)` dependency is present.
- Every dependency resolves to exactly one current effective filing state, or a
  complete member set for declared cross-member fan-in.
- Local filing dependencies are backed by a current `ModeloRecord`, a filed
  `CalculationRevision`, a successful verification report, and values matching
  the stored source observation.
- AEAT-attested dependencies are backed by imported or live-captured official
  evidence, including justificante or equivalent register evidence, and carry
  enough metadata to audit the external source.
- Divergence between local calculated values and AEAT-attested filed values is
  blocking until explicitly reconciled through a typed reconciliation decision.
- Missing, stale, superseded, duplicate, unverifiable, manually-entered, or
  storage-degraded upstream sources do not produce filing-grade values. They
  may produce diagnostics or non-filing preview data only if the surface labels
  the result as incomplete/non-filing-grade.

The ADR should also reject the current "operator manual blank" fallback for
filing-grade cross-period dependencies. Manual override can remain a draft or
diagnostic affordance, but not a path to `VERIFICADO_COMPLETO`, export, or
filing-grade status for values whose legal basis is prior filed history.

## Implementation Direction

The implementation should introduce a typed cross-period dependency proof
instead of overloading `CalculationObservationRepository` with state inference.

The proof should be built by an application-layer service that consumes only
public package surfaces:

- Registry dependency requirements from the selected `RegistrySnapshot`.
- `CalculationObservationRepository` for observed casilla values.
- `ModeloRecordCatalogueRepository` for current/superseded filing state and
  external evidence.
- `CalculationRevisionCatalogueRepository` and
  `VerificationReportCatalogueRepository` for local verification and filed
  revision linkage.
- Persisted live-filed declaration artefacts or imported external evidence
  records for AEAT-attested dependencies.

The service should return strict typed records:

- dependency requirement rows derived from the registry;
- dependency evidence rows tying each requirement to filing state and
  observation values;
- clean-state verdicts with blocking reasons;
- source fingerprints and evidence references for staleness and audit.

`PreviousFilingSourceResolver`, relation prefill, verification, export, and
file flows should consume this proof for filing-grade operations. The
lower-level prefill helpers can remain as preview/building blocks if their
results are explicitly marked non-authoritative until the proof passes.

## Verification Implications

Tests should be real-behavior tests using real repositories and registry
snapshots. Required negative cases include:

- missing required upstream period refuses verification/export for every
  affected source kind;
- superseded upstream filing refuses downstream clean state;
- local source observation without filing-record linkage refuses;
- AEAT-attested observation without justificante/register/live evidence refuses;
- mismatched local calculation and AEAT evidence refuses until reconciled;
- cross-member group aggregation refuses incomplete member coverage;
- storage degradation produces a blocking diagnostic, not a silent zero or
  operator-manual fallback.

Positive tests should cover more than Modelo 390. At minimum they should span a
quarterly-to-annual summary chain, a prior-period carry-forward, a prior-year
baseline, and a cross-member fan-in if that surface remains in scope.

## Open Questions

The ADR should decide whether the clean-state gate blocks initial calculation
itself, or whether a calculation may produce a non-filing-grade draft while
verification/export/file hard-refuse. The safer filing system behavior is to
block automatic calculation for source-owned values unless the operator
explicitly requests a preview/incomplete mode.

The ADR should decide how external AEAT evidence is represented durably. The
current `ExternalEvidence` record is attached to filing records, while live
capture persists artefact manifests separately and calculation observations
carry only `source_kind`. A durable clean-state proof likely needs an explicit
evidence-reference model shared by imported and live-captured sources.

The ADR should decide whether `app_filing` remains acceptable as a source kind.
If it does, it must mean "locally filed and current with a matching
ModeloRecord", not merely "a test or helper saved an observation under this
source kind."
