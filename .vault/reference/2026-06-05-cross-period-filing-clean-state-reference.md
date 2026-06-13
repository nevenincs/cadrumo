---
tags:
  - '#reference'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-02-modelo-filing-ledger-snapshot-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---

# `cross-period-filing-clean-state` reference: `current implementation evidence`

This reference records the audited code surfaces for the uniform clean-state
gate required by cross-period modelo dependencies. Modelo 390 is only one
example; the affected class includes direct `previous_filing` bindings,
registry relations, prior-period carry-forward, prior-year baselines,
annual summaries, and cross-member fan-in.

## Strict domain resolver

- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`
  exposes `previous_filing_observation_requirements` and
  `resolve_previous_filing_binding_values`.
- `resolve_previous_filing_binding_values` refuses incomplete direct
  dependency input once it is handed the expected observation set. Non-group
  selectors require exactly one matching observation for each required source
  filing. `per_grupo_member` selectors require at least one member observation
  and each required source casilla.
- This means the registry layer can fail closed, but only after callers supply
  the expected observations. It is not currently the end-to-end filing-grade
  gate.

## Application prefill is permissive

- `src/aeat/application/calculations/_binding_prefill.py` resolves
  `previous_filing` bindings from `CalculationObservationRepository`.
- The prefill contract states that unavailable bindings are skipped silently
  and that strict enforcement is the caller's choice via report coverage.
- When no observations are gathered, `resolve_bindings_from_local_store`
  returns an empty `BindingPrefillReport` instead of a blocking diagnostic.
- The helper gathers available observations by registry requirement and passes
  those to the strict domain resolver. Absence can therefore remain a preview
  or blank-cell state instead of a verification/file refusal.

## Registry relations are also permissive

- `src/aeat/application/calculations/_relation_prefill.py` resolves relation
  sources from the observation repository.
- The relation prefill contract says missing local sources become
  `RelationValue(value=None)` with operator-manual provenance so the engine
  emits a blank cell.
- `_resolve_available_relation_values` catches `RegistryValidationError` for
  incomplete source observations, logs that the relation remains
  operator-manual, and continues.
- `RelationPrefillSourceResolver` returns only non-null resolved relation
  values through the source mesh; unresolved dependencies do not become a
  blocking filing-grade verdict.

## Calculation can accept manual previous-filing values

- `src/aeat/application/modelo/_binding_resolution.py` merges profile,
  backend, borrador, relation, and caller binding values for
  `calculate_modelo_revision`.
- `resolve_bound_casilla_inputs_for_available_bindings` projects only
  bindings that are already present.
- `_lift_previous_filing_casilla_overrides_to_bindings` promotes operator
  casilla overrides for previous-filing-bound casillas into binding values
  when a binding was otherwise unresolved.
- This is acceptable for a draft or diagnostic preview only if later
  verification/export/file gates refuse unresolved or manually substituted
  cross-period dependencies.

## Verification, export, and file lack a uniform dependency proof

- `src/aeat/application/modelo/_actions.py` contains
  `calculate_modelo_revision`, `verify_modelo_revision`, and
  `file_modelo_revision`.
- `verify_modelo_revision` checks revision state, content integrity, required
  manual casillas, registry predicates, workflow gates, ledger snapshot
  evidence, and IVA wallet decisions. It does not generally require every
  cross-period dependency to resolve to a current filed state with AEAT
  evidence and reconciliation.
- `file_modelo_revision` requires `VERIFICADO_COMPLETO` and runs workflow and
  IVA wallet checks, but it inherits the absence of a general upstream
  clean-state gate.
- `src/aeat/application/modelo/_export.py` accepts verified-complete and filed
  revisions, refuses missing ledger export evidence for ledger-derived
  revisions, and rebuilds the export from the revision. It does not impose an
  independent upstream cross-period clean-state proof.

## Filing records carry stronger state than observations

- `src/aeat/domain/modelos/_filing_record.py` defines
  `ModeloRecordStatus.VIGENTE` and `ModeloRecordStatus.SUPERSEDIDO`, with at
  most one current record per bucket, modelo, filing year, and period.
- `ModeloRecord` carries `aeat_accepted` and optional `ExternalEvidence`.
  `ExternalEvidenceKind` includes official evidence classes such as AEAT
  justificante PDF, CSV register, and live capture.
- These filing-record concepts are not consulted by current prefill resolvers
  before producing cross-period source values.

## Filing-grade evidence requires justificante verification

- The clean-state service distinguishes general external evidence from
  filing-grade verificante evidence. AEAT CSV register evidence can support
  filing history diagnostics, but it is not sufficient to unlock a downstream
  cross-period filing-grade workflow.
- Downstream dependencies now require justificante PDF evidence or AEAT live
  filed capture evidence before an upstream filing can satisfy clean-state
  verification. A current AEAT-accepted source filing with CSV-only evidence is
  classified with `missing_justificante_verification`.
- This preserves the product distinction between an app-local ready-to-file
  calculation and the real-world AEAT submission state. Calendar and workflow
  surfaces can show both, but filing-grade cross-period dependencies must lock
  against the real-world AEAT state.

## Live and import paths create evidence, but do not join it into a proof

- `src/aeat/application/live/__init__.py` exposes
  `capture_source_filed_data` and `persist_filed_calculation_observation`.
- `persist_filed_calculation_observation` promotes AEAT filed-declaration
  observations into `CalculationObservationRepository` with
  `source_kind="aeat_sede_justificante"`.
- `src/aeat/application/modelo/_actions.py` exposes
  `import_external_filing_evidence`, which creates a filed calculation
  revision and a current `ModeloRecord` with `aeat_accepted=True` and
  `external_evidence` populated.
- The observation repository and filing-record catalogue are not yet joined by
  a durable cross-period dependency proof that can answer whether an upstream
  filing is clean for downstream filing-grade calculation.

## Observation storage is value-centric

- `src/aeat/application/calculations/_observations_repository.py` stores a
  `_ObservationEnvelopePayload` containing `RegistryModeloObservation`,
  `captured_at`, `source_kind`, and optional `member_nif`.
- `source_kind` is a free string described as `app_filing`,
  `aeat_sede_justificante`, or `operator_manual`.
- The envelope does not persist filing record id, external evidence id,
  AEAT listing row status, captured artifact reference, reconciliation
  verdict, verification report id, or current/superseded status.
- This makes the observation store useful for value replay, but insufficient
  by itself as filing-grade legal proof.

## Registry surface is broader than Modelo 390

- Registry data declares direct `previous_filing` bindings in modelos including
  100, 130, 131, 180, 190, 193, 200, 202, 303, 353, and 390.
- Registry data declares period-aligned relations or previous-period sources in
  modelos including 100, 180, 190, 193, 200, and 202.
- Continuity tests use `source_kind="app_filing"` across many affected
  modelos, including 390-from-303, 190-from-111, 193-from-123,
  180-from-115, 202 prior-period/prior-year, 200 prior-year carry-forward,
  303 carry-forward, 353 group aggregation, and additional fidelity models.
- Existing tests validate numerical continuity and repository roundtrip, but
  they do not establish a uniform filing-grade refusal when the upstream
  state is missing, stale, superseded, not AEAT-attested, or unreconciled.

## Existing adjacent gates

- The amendment path in `src/aeat/application/modelo/_actions.py` already
  requires imported official evidence on an external baseline before creating
  an amendment. That is a useful precedent for evidence-gated state.
- IVA wallet reconciliation already has an application-level decision object
  and persisted decision repository. That pattern is useful for a
  cross-period dependency proof, but it is narrower than the uniform filing
  history problem.
- Ledger snapshot/export gates prove that filing-grade evidence can be checked
  at verification/export boundaries without moving registry purity into
  storage-facing code.

## RAG limitation

VaultSpec semantic search could not be used during this audit because the
local Qdrant store was locked by another process. The audit used `fd`, `rg`,
VaultSpec templates, existing vault ADR/research/reference files, and direct
code reads instead.
