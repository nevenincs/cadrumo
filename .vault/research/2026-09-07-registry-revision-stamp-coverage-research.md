---
tags:
  - '#research'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d9e0fb18ca85868140384432d3504b68a316b397deecf8ea3072676a0b12b562'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-reference]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
---

# `registry-revision-stamp-coverage` research: `Stamp-and-reconfirm coverage and canonical migration`

The question is whether the accepted stamp-and-reconfirm rule covers every
durable carrier whose values were interpreted through a registry revision, and
how already-persisted unstamped rows can cross the new boundary. The sweep found
twelve value-carrier families plus the official-export custody envelope. Only
three value carriers have complete coordinates, and the nested M303 handoff has
complete source and target coordinates. The gap therefore extends beyond
`CalculationRevision`. The accepted ADR resolves migration policy strictly:
only provable conversion may emit canonical rows, and no legacy row shape is
admitted at runtime.

## Findings

### The defect is a carrier-family omission, not an M349 special case

`CalculationRevision` persists registry-derived casilla membership and values but
only retains `work_unit_id`; a sound coordinate can be recovered from the
`WorkUnit` natural identity, yet a bare revision reader cannot lawfully reach an
adapter or registry authority to perform that join. `VerificationReport`,
`ModeloReconciliationRecord`, and `ReviewPackageManifest` repeat the same indirect
identity pattern. `Borrador100Snapshot`, the IVA compensation carriers,
`ProrrataRegisterEntry`, and the export custody envelope hold partial or opaque
coordinates. The exact inventory and boundary rationale are recorded in the
related reference.

The sweep also found `FiledDeclaracionObservation`: it persists registry-parsed
casillas with only an optional opaque `RegistrySnapshotId`. Because the digest
does not retain modelo/year/period/revision as typed fields, a read cannot pass
it to the shared gate. The canonical change replaces that deprecated partial
identity with required `RegistrySnapshotRef`; it does not retain both shapes.

M349 demonstrates the consequence. Write-side membership comes from
`export_layouts[].records[].row_field_casilla_ids`; read-side membership is
reconstructed with the `op.` and `rect.` prefixes after the authoritative
revision coordinate has been discarded. The proposed identifier-grammar ADR
predicts this failure mode, but grammar normalisation alone cannot reconnect an
old value with the revision that produced it.

### Existing complete carriers show the target shape

`ModeloDraft` carries the canonical `RegistrySnapshotRef` directly.
`M145CommunicationRecord` carries the same four components locally and validates
them on read. `M303RegimenSimplificadoAnnualSummaryHandoff` carries complete
source and target coordinates and re-resolves both exactly. The observation
envelope distributes the same coordinate between its observation identity and
`stamped_revision_id`. These are compatible precedents; the canonical type should
be preferred where the enclosing schema permits it, while nested payloads inherit
one owning stamp rather than redeclaring it.

### Re-confirmation already has one application gate

The accepted calculation-engine foundations plan closed W01.P02.S03 with
write-time stamping and W01.P02.S04 with read-time re-confirmation. Current carry
readers converge on `revision_carry_outcome`, and cross-period clean state maps
divergence to `REGISTRY_REVISION_DIVERGENCE`. Extending coverage must route every
read through that gate or an evolution of its signature; a parallel gate would
recreate the split authority the accepted decision removed.

The current implementation accepts a required `RevisionId`, and the current
observation envelope also requires its stamp. That is stricter than the closed
plan's stated legacy behavior, which said a missing stamp advises while a
divergent stamp blocks. The legacy arm described by the plan is therefore no
longer representable in the present gate signature. Restoring a typed missing
state, defining where it may pass, and deciding when that allowance ends are part
of the migration decision rather than an implementation inference.

### Fixed official formats need a stamped owning envelope

An official export byte stream cannot acquire an application field without
changing the external format. The coordinate instead belongs in the application
manifest or custody record that owns the immutable bytes. This follows the same
boundary as nested calculation evidence: one authoritative stamp at the nearest
durable application-owned envelope, with validation that identifiers in the
payload agree with it.

### Three migration policies remain credible

Strict cutover rejects every unstamped carrier until it is recaptured or
backfilled. It is simplest and strongest, but can make valid historical filings
unavailable when their old revision can no longer be proved from the detached
artefact alone.

Deterministic backfill stamps rows only where durable joins prove the exact
coordinate, such as `CalculationRevision -> WorkUnit`; ambiguous or detached rows
remain explicitly legacy. This preserves evidence quality but cannot cover every
carrier.

Legacy admission lets the shared gate emit a structured advisory for a missing
stamp while continuing the read, and still blocks a present-but-divergent stamp.
It preserves old rows but is unsafe if filing-decision surfaces can treat the
advisory as confirmed data indefinitely.

The evidence identifies the hybrid as the compatibility-maximizing option, but
operator adjudication rejected it. The accepted ADR permits proof-only conversion
and rejects unresolved absence at schema or repository admission, including
historical viewing paths; there is no runtime legacy state or advisory arm.

### Scope exclusions do not weaken the coverage rule

Raw ledger, invoice, profile, Sede, and observation records are evidence inputs,
not interpretations selected from a registry revision. `WorkUnit` is a coordinate
anchor rather than a derived-value carrier. Transient workspace projections do
not need independent persistence stamps. The two state-axis mapping locators
flagged in the mission were not used because state aggregation does not determine
registry-derived-value provenance.

## Sources

- `src/cadrumo/domain/calculations/registry/schema_references.py:149`
- `CalculationRevision` in `src/cadrumo/domain/modelos/calculation_revision.py`
- `WorkUnit` in `src/cadrumo/domain/modelos/work_unit.py`
- `ObservationEnvelopePayload` in
  `src/cadrumo/application/calculations/observations_repository.py`
- `revision_carry_outcome` in
  `src/cadrumo/application/calculations/revision_carry_gate.py`
- `CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE` in
  `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `src/cadrumo/application/calculations/_calculation_modelo_adjustments.py:319`
- `src/cadrumo/application/calculations/calculation_actions.py:556`
- `src/cadrumo/application/modelo/calculation.py:215`
- `src/cadrumo/domain/modelos/verification_report.py:235`
- `src/cadrumo/domain/filing/schema.py:312`
- `src/cadrumo/application/live/borrador_100.py:67`
- `src/cadrumo/domain/iva_compensation/carry_forward.py:51`
- `src/cadrumo/domain/iva_compensation/reconciliation.py:129`
- `src/cadrumo/domain/prorrata_register/register.py:203`
- `src/cadrumo/application/modelo/m145_communication_records.py:247`
- `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py:56`
- `src/cadrumo/application/modelo/reconciliation_records.py:161`
- `src/cadrumo/application/modelo/review_package.py:121`
- `src/cadrumo/application/filing/export_proof.py:45`
- `.vault/plan/2026-06-10-calculation-engine-foundations-plan.md:41`
- `.vault/plan/2026-06-10-calculation-engine-foundations-plan.md:45`
- `.vault/plan/2026-06-10-calculation-engine-foundations-plan.md:46`
