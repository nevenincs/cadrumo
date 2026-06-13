---
tags:
  - '#adr'
  - '#cross-period-calculation-guards'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-cross-period-calculation-guards-research]]'
  - '[[2026-06-05-cross-period-calculation-guards-reference]]'
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-06-02-modelo-filing-ledger-snapshot-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---

# `cross-period-calculation-guards` adr: `filing-grade cross-period dependencies require clean prior filing proof` | (**status:** `accepted`)

## Problem Statement

Cross-period modelo calculations currently consume prior filing observations,
relations, prior-year facts, annual rollups, and group-member fan-in through
calculation observation helpers that can resolve available values without
proving that the upstream filings are complete, current, verified, AEAT
accepted, justificante-backed, and reconciled with the local calculations that
created or imported those values.

Modelo 390 exposed the issue because it aggregates filed IVA periods, but the
problem is not Modelo 390-specific. Registry discovery shows the affected class
includes modelos whose definitions use `previous_filing` bindings, period
aligned relations, prior-period carry-forward, prior-year baselines, annual
summary dependencies, and cross-member filed observations.

A dependable filing system cannot treat arbitrary local history, operator
manual blanks, or latest available observations as filing-grade truth. When a
target modelo depends on prior filed declarations, the application must prove
that the filing history it consumes is the same filing history accepted or
attested by AEAT, and that the AEAT-attested values reconcile with the local
calculation values used by the downstream target.

## Considerations

The existing calculation substrate already distinguishes useful pieces of the
problem. `previous_filing` binding prefill, relation prefill, and multiyear
resolution can discover prior observations and source coverage. The observation
repository records source kind and captured timestamp. Filing records carry
current or superseded state, AEAT acceptance, and external evidence kinds such
as justificante PDF, CSV register, and live capture. Verification reports can
persist blocking findings.

Those parts are not yet tied into one filing-grade proof. A stored calculation
observation with `source_kind = "app_filing"` or
`source_kind = "aeat_sede_justificante"` does not by itself prove that the
source filing record is current, that the local revision was filed, that the
verification report was complete, that the justificante values match local
casillas, or that every registry-required period/member has been covered.

The existing source connectivity ADR already rejects plausible zero output from
missing source resolvers. The filing ledger snapshot ADR already makes filed
revisions auditable against their ledger source state. The live IVA remote
evidence ADR already treats missing or divergent official evidence as blocking
for one IVA authority. This ADR extends those principles uniformly to every
cross-period dependency class.

Missing evidence and divergent evidence are different operator states. Missing
prior filings, draft local revisions, superseded filings, local-only filing
observations, absent justificante evidence, incomplete group-member coverage,
storage degradation, duplicate effective source filings, and remote/local
casilla drift must be classified separately. All are blocking for filing-grade
calculation, verification, export, and filing readiness until repaired or
resolved through a typed reconciliation decision.

## Constraints

The dependency graph must be registry-derived from the selected
`RegistrySnapshot`. Callers cannot pass a smaller ad hoc dependency set for a
filing-grade workflow.

The rule is uniform across source classes. It applies to every modelo and
workflow that consumes prior filings through `previous_filing`, registry
relations, prior-period carry-forward, prior-year baseline, annual summary
rollup, cross-member filed observation, or any future source resolver that
declares filed-history dependency semantics.

The guard belongs in the application layer. Registry and domain calculation
code may define source selectors, relation requirements, and pure observation
validation, but repository reads, live evidence lookup, filing-record lookup,
and workflow refusal remain application concerns.

Application consumers must use package public interfaces when importing across
top-level package boundaries. The implementation must not make high-level
application or entrypoint code traverse into private modules of domain or
adapter packages.

Boundary payloads must be strict typed models. A clean-state verdict cannot be
an unstructured string list or an inferred side effect of missing values.

Tests must use real repositories, real registry snapshots, and production
services. They must not use mocks, stubs, fakes, monkeypatches, `skip`, `xfail`,
or tautological reimplementation of tax calculation logic.

Parent features are stable enough to depend on, but not complete enough to
delegate the decision. Source mesh connectivity, filing ledger snapshots, live
capture persistence, filing records, and verification reports are accepted
architectural surfaces. None currently binds the uniform cross-period
clean-state proof, so this ADR is an additive guard contract rather than a
reinterpretation of those ADRs.

## Implementation

Introduce an application-layer cross-period dependency proof service. The
service builds a typed requirement set from the selected registry snapshot and
the target modelo, filing year, period, and optional member context. It must
include every filed-history dependency implied by registry `previous_filing`
bindings, relation source requirements, prior-period carry-forward, prior-year
baseline, annual rollup, and cross-member fan-in rules.

The service returns strict typed records:

- dependency requirement rows naming the upstream modelo, filing year, period,
  relation or binding origin, expected casillas, and member identity where
  relevant;
- dependency evidence rows tying each requirement to calculation observations,
  current filing records, calculation revisions, verification reports, external
  evidence references, source fingerprints, and reconciliation status;
- a clean-state verdict with blocking reason codes and operator-facing
  diagnostics.

Clean-state proof is satisfied only when every required dependency is present
and each dependency resolves to exactly one current effective filing state, or
to the complete declared member set for cross-member fan-in.

For local internal filings, the dependency must be backed by a current
`ModeloRecord`, a filed `CalculationRevision`, a complete successful
verification report for that revision, and source observation values that match
the filed revision values consumed by the downstream dependency.

For AEAT-attested external filings, the dependency must be backed by imported
or live-captured official evidence such as justificante PDF, CSV register, or
live filed-declaration capture. The evidence must carry enough metadata to
audit the external source and must be reconciled against the relevant local
calculation, unless the filing is explicitly imported as an external baseline
with an AEAT-accepted record and typed reconciliation state.

Filing-grade workflows must fail closed when the clean-state verdict is not
complete. Verification cannot promote the target revision to
`VERIFICADO_COMPLETO`; export cannot emit a filing-grade artefact; filing
readiness cannot proceed; and automatic calculation for source-owned values
must refuse unless the surface is explicitly a diagnostic or draft preview.
Preview flows may still calculate incomplete values only when the result is
clearly marked non-filing-grade and cannot be promoted, exported, or filed
without a complete clean-state proof.

The existing lower-level prefill helpers may remain as resolver building
blocks, but their output is not authoritative for filing-grade use until the
proof service passes. Operator manual blanks or manual overrides may remain a
draft affordance, but they are not a legal substitute for filed-history
evidence where the registry declares a prior filing dependency.

Verification findings must classify at least these blocking states: missing
dependency, duplicate effective dependency, superseded dependency, unfiled
local revision, incomplete upstream verification, missing filing record link,
missing external evidence, missing justificante or equivalent register
reference, unresolved source storage, incomplete member coverage, stale
evidence, and remote/local value divergence.

## Rationale

Cross-period tax calculations are only dependable when the downstream engine
uses the same upstream filing values that AEAT has received or attested. A
calculation based on arbitrary local observations can look arithmetically
correct while being legally unsafe if the prior filing was never accepted, was
superseded, lacks justificante evidence, or differs from the local casilla
values.

The fail-closed proof service preserves the hexagonal split. Registry metadata
continues to define what is required, pure calculation remains storage-free,
and application services prove filing state by joining observations, filing
records, revisions, verification reports, and official evidence.

This also gives operators a repair path. A single blank prefill or generic
unresolved binding message does not tell them whether to file a missing period,
refresh live evidence, import a justificante, reconcile a mismatch, or repair
storage. Typed blocking states make the failing layer explicit.

## Consequences

Filing-grade workflows become more conservative. Existing scenarios that
previously produced an annual or cross-period draft from partial observation
history will now block verification, export, and readiness until upstream
filings are clean.

Some operator flows will need explicit preview language. A draft calculation
can still help diagnose missing history, but it must not be confused with a
verified, exportable, or file-ready declaration.

The implementation will add a new application service and typed verdict model,
plus integration points in calculation, verification, export, and filing
readiness. It will likely require migration from weak observation-only state to
evidence-linked filing records for imported and live-captured AEAT filings.

Tests become broader because the behavior is cross-model. Negative coverage
must span more than Modelo 390 and must exercise missing, superseded,
local-only, missing-evidence, mismatch, and incomplete-member states through
real repositories.

The project gains a durable legal-grade invariant: filed-history dependencies
are not just values, they are proven filing states.

## Codification candidates

- **Rule slug:** `cross-period-dependencies-require-clean-filing-proof`.
  **Rule:** Any filing-grade workflow for a modelo that consumes prior filed
  history must fail closed unless every registry-derived upstream dependency is
  current, filed or externally imported, AEAT-attested, justificante or
  register evidenced, and reconciled with the local calculation state.
