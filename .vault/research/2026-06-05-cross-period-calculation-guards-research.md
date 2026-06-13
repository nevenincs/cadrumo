---
tags:
  - '#research'
  - '#cross-period-calculation-guards'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-cross-period-calculation-guards-reference]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-06-02-modelo-filing-ledger-snapshot-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---

# `cross-period-calculation-guards` research: `uniform clean-state requirement for prior-filing-dependent modelos`

This research audits whether cross-period modelo calculations already enforce a
clean prior-filing state, and determines the decision needed to make annual,
multi-period, prior-year, prior-modelo, and group-fan-in calculations filing
grade.

## Findings

Cross-period calculation is a general source class, not a Modelo 390 special
case. Registry discovery found `previous_filing` bindings in modelos 100, 130,
131, 180, 190, 193, 200, 202, 303, 353, and 390. Registry relations with
`period_alignment` exist in modelos 100, 180, 190, 193, 200, 202, and 303.
Those definitions include same-year quarterly or monthly rollups, annual
summary dependencies, prior-period cumulative payments, prior-year baselines,
IVA carry-forward recurrence, and group-member aggregation.

The current calculation substrate resolves available prior observations but
does not require a clean state. `resolve_bindings_from_local_store` skips
missing previous-filing bindings and leaves strict enforcement to callers.
`resolve_relations_from_local_store` emits unresolved relation values rather
than hard-failing when the local observation store lacks complete coverage.
`MultiYearResolver` reports missing years but makes refusal, prompting, live
fallback, or zero-fill a caller decision.

The observation store is too weak to prove filing-grade source state by itself.
`CalculationObservationRepository` persists `RegistryModeloObservation`,
`captured_at`, `source_kind`, and optional member identity. It can distinguish
`aeat_sede_justificante` from `app_filing`, but it cannot prove the upstream
filing record was current, locally verified, AEAT-accepted, externally evidenced,
or reconciled against the local calculation revision.

The codebase already has partial official-evidence infrastructure. Live filed
capture can fetch source filings required by a target snapshot and persist them
as `aeat_sede_justificante`. Filing records can carry external evidence for
justificante PDFs, CSV registers, and live capture. Verification reports can
persist blocking findings. The missing piece is a guard that ties these sources
together before a cross-period calculation is considered filing grade.

Existing ADRs bind adjacent behavior but not this rule. Source connectivity
binds a source mesh and refuses silent source resolver gaps. Filing ledger
snapshots bind immutable local ledger provenance. Calendar live integration
binds local projection of captured live reads. Live IVA remote evidence binds
blocking behavior for one IVA compensation authority. No existing accepted ADR
requires every cross-period dependency to be complete, verified, current,
AEAT-attested, and reconciled.

The dependable tax-filing behavior is the stronger clean-state rule. When a
modelo depends on prior filings, the target calculation must not treat arbitrary
local history as filing-grade truth. It must prove, per required upstream
filing, that the applicable filing exists, the locally calculated revision is in
a filed or externally imported filed state, the filing record is current and not
superseded, the filing has AEAT acceptance evidence or live justificante capture,
and the captured AEAT casilla values reconcile with the local calculation values
for the outputs consumed by the target dependency.

Missing evidence and divergence are different states. Missing source filings,
unverified local drafts, local-only filed records without AEAT acceptance,
missing justificante values, stale superseded filings, and remote/local casilla
drift must be classified separately so the operator can repair the right layer.
All of them should block filing-grade calculation, verification, export, and any
future filing readiness for a target modelo that requires those dependencies.

## Recommendation

Create a binding ADR for `cross-period-calculation-guards` with this decision:
all registry-declared cross-period dependencies are filing-grade only when a
complete dependency coverage report proves each required upstream filing is
current, verified or externally imported, AEAT-attested by justificante, CSV, or
live capture, and reconciled with local calculation observations for the
required casillas. Calculation may still produce a diagnostic or draft preview
when explicitly requested, but `verify`, export, readiness, and filing-grade
calculation must refuse until the clean-state report is complete.

The implementation should add a typed guard service under the application
calculation boundary, reuse registry requirement discovery, consume source
observations and filing records through top-level package exports where
available, emit verification findings for incomplete cross-period evidence, and
add real-behavior tests over actual repositories. Tests must not use mocks,
stubs, monkeypatches, or hand-reimplemented business logic.
