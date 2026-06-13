---
tags:
  - '#reference'
  - '#cross-period-calculation-guards'
date: '2026-06-05'
modified: '2026-06-05'
related: []
---

# `cross-period-calculation-guards` reference: `current cross-period implementation audit`

## Scope

This reference records the implementation surfaces audited for the cross-period
calculation guard decision. The target behavior is uniform across all modelos
whose registry definitions consume previous periods, previous years, previous
modelos, or filed remote state. Modelo 390 is only one example.

## Current Implementation Surfaces

`src/aeat/application/calculations/_binding_prefill.py` resolves
`source = "previous_filing"` bindings from `CalculationObservationRepository`.
Its module docstring distinguishes binding resolution from relation resolution
and explicitly states that Modelo 390 uses previous-filing bindings while Modelo
200 uses relations for similar aggregation semantics. The important current
policy appears in `resolve_bindings_from_local_store`: missing bindings are
skipped, the engine receives only resolved values, and strict enforcement is
left to callers through coverage inspection.

`src/aeat/application/calculations/_relation_prefill.py` resolves registry
relations from prior filing observations. When local observations are missing,
the resolver returns relation values with `value=None` and operator-manual
provenance so export/calculation surfaces can emit blank cells instead of a hard
failure. `_resolve_requirement_value` can detect incomplete source observation
sets, but `_resolve_available_relation_values` downgrades unresolved relations
to missing prefill coverage instead of making the target uncalculable.

`src/aeat/application/calculations/_multi_year.py` provides generic prior
filing scans and the source-mesh `previous_filing` resolver. The module
documents the affected model families: Modelo 200, Modelo 303, Modelo 180,
Modelo 190, Modelo 193, and Modelo 390. It also states that missing prior years
are not invented; the returned report is shorter and callers decide whether to
refuse, prompt, fall back to live state, or zero-fill.

`src/aeat/application/calculations/_observations_repository.py` persists
`RegistryModeloObservation` records with `captured_at`, `source_kind`, and
optional group-member widening. It does not persist a filing-record pointer,
verification-report pointer, justificante/evidence pointer, external evidence
kind, reconciliation verdict, or source completeness state. The store can record
`source_kind` values such as `app_filing`, `operator_manual`, and
`aeat_sede_justificante`, but the repository schema alone cannot prove that a
prior filing was verified, presented, accepted by AEAT, and reconciled.

`src/aeat/application/live/__init__.py` exposes `capture_source_filed_data` and
`persist_filed_calculation_observation`. These functions can capture filed
source declarations required by a target filing's registry dependencies and
promote AEAT filed-declaration observations into the calculation observation
store with `source_kind = "aeat_sede_justificante"`. `_persist_latest_filed_calculation_observations`
selects the latest captured observation per modelo, year, and period.

`src/aeat/domain/modelos/_filing_record.py` models internal and externally
observed filing records. A `ModeloRecord` can carry `aeat_accepted = True` and
`ExternalEvidence` with kinds `aeat_justificante_pdf`, `aeat_csv_register`, or
`aeat_live_capture`. This proves the filing-record layer already has an external
evidence vocabulary, but that vocabulary is not connected to
`CalculationObservationRepository` coverage checks.

`src/aeat/domain/modelos/_calculation_revision.py` models the calculation
revision lifecycle. `VERIFICADO_COMPLETO`, `PRESENTADO`, and
`PRESENTADO_SUPERSEDIDO` prove local calculation/filing state, but the revision
does not by itself prove AEAT external acceptance unless paired with an accepted
filing record or imported external evidence.

`src/aeat/domain/modelos/_verification_report.py` exposes finding kinds for
missing required casillas, reconciliation mismatches, unresolved bindings,
invalid waivers, and blocking rules. There is not yet a distinct finding kind
for incomplete cross-period evidence, local-only prior filing evidence, or
remote/local justificante divergence.

`src/aeat/_data/registry/aeat/modelos` declares current cross-period consumers.
Fixed-string registry discovery found `previous_filing` bindings in modelos
100, 130, 131, 180, 190, 193, 200, 202, 303, 353, and 390. Registry
`period_alignment` relations were found in modelos 100, 180, 190, 193, 200,
202, and 303. This means the behavior is not a Modelo 390-only issue.

## Existing Decision Coverage

`.vault/adr/2026-05-20-calculation-source-connectivity-adr.md` binds the source
mesh and says missing source resolvers must not produce plausible zero outputs.
It does not define a clean-state rule for prior filing source quality.

`.vault/adr/2026-06-02-modelo-filing-ledger-snapshot-adr.md` binds immutable
ledger snapshots for calculation revisions. It does not bind external AEAT
acceptance or justificante reconciliation for prior filing observations.

`.vault/adr/2026-05-26-live-iva-remote-evidence-reconciliation-adr.md` binds a
stronger evidence model for IVA compensation wallet state. It says missing,
stale, unreadable, or divergent remote evidence can block filing-grade output,
but the scope is IVA compensation, not every cross-period modelo dependency.

`.vault/adr/2026-06-04-calendar-live-filing-integration-adr.md` binds local
projection of persisted live-read state and bulk filed-declaration capture. It
does not require those captures before cross-period calculation or verification.

## Audit Conclusion

The codebase already has the parts needed to implement a strong clean-state
guard: registry dependency discovery, live source capture, calculation
observation persistence, filing records with external evidence, verification
reports, and source mesh provenance. The missing architectural contract is a
uniform guard that classifies cross-period dependencies as filing-grade only
when required upstream filings are complete, verified, current, AEAT-attested,
and reconciled against the local calculation values.
