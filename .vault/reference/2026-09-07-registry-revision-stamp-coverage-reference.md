---
tags:
  - '#reference'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:81785c856786af922765af3981b7b3371e5bd965874cdacf1a66b40b1f116a9a'
related:
  - "[[2026-06-10-period-revision-resolution-adr]]"
---

# `registry-revision-stamp-coverage` reference: `Persisted registry-derived value carrier inventory`

## Summary

This inventory covers application-owned durable artefacts whose persisted values,
membership, meaning, or provenance are selected or materialised from a
`RegistrySnapshot` or `ModeloRevision`. Registry source declarations, generated
registry material, transient projections, and raw source evidence are outside the
coverage set. A complete coordinate is the canonical `RegistrySnapshotRef`
quadruple `(modelo, revision_id, modelo_year, period)`.

## Persisted carrier inventory

| Carrier | Registry-derived payload | Persisted coordinate | Coverage result |
|---|---|---|---|
| `CalculationRevision` | Casilla outputs, inputs, bindings, relation values, repeated-row values, observations, and provenance | Required full `RegistrySnapshotRef`, validated against its `WorkUnit` | Complete |
| `VerificationReport` | Registry expectation and casilla verification outcomes | Required full `RegistrySnapshotRef`, copied from and validated against `CalculationRevision` | Complete |
| `ModeloDraft` | Filing draft values and registry-governed declaration shape | Full `RegistrySnapshotRef` | Complete |
| `ObservationEnvelopePayload` | Persisted carry observations | Observation supplies modelo/year/period and `stamped_revision_id` supplies revision | Complete, distributed across the envelope |
| `FiledDeclaracionObservation` | Encrypted AEAT-captured casillas and headers | Required full `RegistrySnapshotRef`; the deprecated opaque digest field is rejected | Complete |
| `Borrador100Snapshot` | Registry-profile `BindingId` values | Required full `RegistrySnapshotRef` | Complete |
| `IvaCompensationPeriodState` | Amounts derived from M303 casillas | Required full M303 `RegistrySnapshotRef` | Complete |
| `IvaCompensationReconciliationDecision` | Persisted decision later consumed by calculation | Required target and complete source `RegistrySnapshotRef` values | Complete |
| `ProrrataRegisterEntry` | Percentage and volume values derived from filing data | Required tuple of source `RegistrySnapshotRef` values; explicitly empty only for values with no registry-derived source | Complete |
| `M145CommunicationRecord` | Registry-bound communication values | Fixed modelo plus year, period, and revision | Complete, locally distributed |
| `M303RegimenSimplificadoAnnualSummaryHandoff` | Registry-resolved source and target handoff values | Full source and target coordinates | Complete |
| `ModeloReconciliationRecord` | Registry-grounded reconciliation differences | Required full `RegistrySnapshotRef`, copied from the owning `WorkUnit` | Complete |
| `ReviewPackageManifest` | Packaged observations and official export bytes | Required full `RegistrySnapshotRef`, copied from the calculation revision | Complete |
| `FilingExportSecureCustodyRecord` | Digest and custody proof for registry-selected official output | `FilingExportProofCoordinate` contains the draft's required full `RegistrySnapshotRef` | Complete |

`InboundDeclaracionObservation` carries a full `RegistrySnapshotRef`, but it is an
inbound boundary value rather than an additional application-owned persistence
family. Embedded `LedgerFilingSnapshot` and M303 filing evidence belong to their
enclosing `CalculationRevision`; duplicating the coordinate inside each nested
payload would create competing stamps.

## Scope boundaries

`WorkUnit` carries the complete coordinate in its natural identity and was the
authoritative write-side join used to validate new calculation stamps, but it is
not a read-side substitute and does not itself persist a registry-derived value.
`ModeloRecord` and `ModeloHistory` contain lifecycle and
identity data, not derived values. Retention/perception observation repositories,
ledger records, invoices, profiles, and Sede evidence are source facts consumed
by registry interpretation and are not themselves registry-derived artefacts.
Transient workspace projections and response envelopes are not durable carriers.

## Concrete M349 divergence

The authoritative calculation path reads per-row template identifiers from
`revision.export_layouts[].records[].row_field_casilla_ids` in
`_m349_row_field_template_casilla_ids` and applies that set while constructing the
revision. Before this campaign, persisted `CalculationRevision` dropped the
registry coordinate and a bare read in `application/modelo/calculation.py`
substituted `startswith(("op.", "rect."))`. Those prefixes are authored
identifier conventions, not a registry contract: a valid rename could silently
expose a row template as an ordinary value or hide an unrelated identifier. The
proxy and its fixture are now deleted. Reads re-confirm the persisted full
coordinate through `revision_carry_outcome` before exposing the values already
suppressed by the authoritative write-side membership set.

## Canonical admission and re-confirmation

There is no readable unstamped carrier shape. Required Pydantic fields reject
missing coordinates at deserialisation, and repositories reject a divergent
coordinate before preparing a write. In particular, Modelo 303 observations
must contain both the canonical result disposition and compensation basis;
operator-local M303 observations and generic recurrence fallbacks are not
supported persistence paths.

Repository admission and load first require every `CalculationRevision`
coordinate to equal the coordinate reconstructed from its persisted parent
`WorkUnit`; a complete but foreign coordinate is invalid. All consumers that
interpret a persisted `CalculationRevision` payload then cross
`require_calculation_revision_coordinates_current`, which delegates to the one
`revision_carry_outcome` implementation. This includes calculation get/list,
verification, filing, export, amendment, reconciliation, result summary, work
review, declarations-workspace projection, M303/M349 sibling reads, and the
cross-period filing-revision blocker.
Observation consumers use
`require_observation_envelope_coordinates_current`, another carrier adapter over
that same gate, before pulled-filing, prorrata, prior-payment, prior-domiciliation,
live-recapture, or prior-filing approval-fingerprint interpretation. Persisted
ModeloDraft review and CLI loaders, M145 list/read/transition/existing-create,
Borrador list/show, prorrata transition writes, and IVA decision writes similarly
adapt their carrier coordinate to the shared gate. These wrappers translate
refusal into their bounded-context error; none resolve or compare revisions
independently.

Catalogue scans that use only lifecycle identity or counts do not interpret a
registry-derived payload and therefore do not manufacture a carry decision.
Examples are event-history joins, dependency blockers keyed by source
transaction id, and workspace revision counts. They remain outside the read
gate without becoming an alternate registry authority.

## Implementation locators

- Canonical coordinate: `RegistrySnapshotRef` in
  `src/cadrumo/domain/calculations/registry/schema_references.py`.
- Calculation carrier and identity: `CalculationRevision` in
  `src/cadrumo/domain/modelos/calculation_revision.py`.
- Sound recovery join: `WorkUnit` in `src/cadrumo/domain/modelos/work_unit.py`.
- Observation stamp: `ObservationEnvelopePayload.stamped_revision_id` in
  `src/cadrumo/application/calculations/observations_repository.py`.
- Shared read gate: `revision_carry_outcome` in
  `src/cadrumo/application/calculations/revision_carry_gate.py`.
- Calculation carrier adapter: `src/cadrumo/application/modelo/calculation_revision_gate.py`.
- Calculation catalogue parent-coordinate admission:
  `CalculationRevisionCatalogueRepository._require_parent_coordinates`.
- Observation carrier adapter and strict M303 persistence admission:
  `src/cadrumo/application/calculations/observations_repository.py`.
- Draft carrier adapter: `src/cadrumo/application/filing/draft_revision_gate.py`.
- Divergence blocker: `CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE`
  in `src/cadrumo/application/calculations/cross_period_clean_state.py`.
- M349 authoritative membership: `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py:319` and `src/cadrumo/application/modelo/calculation_actions.py:556`.
- M349 gated read: `src/cadrumo/application/modelo/calculation.py`.
- Verification carrier: `src/cadrumo/domain/modelos/verification_report.py:235`.
- Draft carrier: `src/cadrumo/domain/filing/schema.py:312` and `:337`.
- Borrador carrier: `src/cadrumo/application/live/borrador_100.py:67`.
- Filed-declaration observation carrier: `src/cadrumo/adapters/outbound/aeat/sede/schema.py:424` and capture writer `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py:213`.
- IVA compensation carriers: `src/cadrumo/domain/iva_compensation/carry_forward.py:51` and `src/cadrumo/domain/iva_compensation/reconciliation.py:129`.
- Prorrata carrier: `src/cadrumo/domain/prorrata_register/register.py:203`.
- M145 complete precedent: `src/cadrumo/application/modelo/m145_communication_records.py:247`.
- M303 handoff precedent: `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py:56`.
- Reconciliation carrier: `src/cadrumo/application/modelo/reconciliation_records.py:161`.
- Review package: `src/cadrumo/application/modelo/review_package.py:121`.
- Export custody envelope: `src/cadrumo/application/filing/export_proof.py:45` and `:324`.
