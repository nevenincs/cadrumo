---
tags:
  - '#adr'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
related:
  - "[[2026-07-06-cross-domain-continuity-research]]"
---

# `cross-domain-continuity` adr: `Modelo 184 attribution-member source promotion` | (**status:** `accepted`)

## Problem Statement

W09.P41.S307 fires the promotion trigger named by the source-kind deferral
ADR: an operator filing need for Modelo 184. The registry already declares
four `atribucion_member` row bindings, the row model and detail-record resolver
already exist, and S323 added repeatable attribution-entity socio profile facts.
What is missing is the live source resolver that turns those profile facts into
M184 row values. Without it, a sociedad civil or comunidad de bienes can create
an attribution-entity profile but the calculate mesh still treats M184 member
rows as deferred, so the informative declaration cannot be populated from the
profile path.

## Considerations

- The existing deferral ADR explicitly requires a per-kind grounded ADR before
  promoting `atribucion_member`; this record supplies the row taxonomy,
  evidence shape, and detail-record fold semantics.
- The multi-row modelo ADR already made `Modelo184MemberRow` the typed CLI row
  carrier for M184, and the registry helper already exposes
  `AtributionMemberObservation` plus `resolve_atribucion_binding_row_values`.
  Promotion should reuse those types rather than create another row taxonomy.
- The profile schema added by S323 contains socio identity, role, and share
  percentage facts, but not the assigned income/base amount required by the
  M184 row binding. A share percentage is not itself an amount; deriving an
  amount from it would require an independently declared entity total and a
  rounding policy. No such total exists in the profile schema today.
- The source mesh already carries row-indexed binding values, typed detail rows,
  diagnostics, and provenance. No new source channel is needed.

## Considered options

- **Option A: keep `atribucion_member` deferred and rely on `--row miembro`.**
  Rejected: it preserves the advisory floor but does not close S307's profile
  calculation path; the profile can declare socios yet the mesh still ignores
  them.
- **Option B: derive each assigned base from `share_pct` and a guessed total.**
  Rejected: the total is not declared, and a guessed or implicit total would
  silently fabricate an amount the official row reports explicitly.
- **Option C: add a narrow per-socio assigned-base profile fact and promote a
  profile-backed resolver.** Chosen: it makes every reported row field
  explicit, reuses the existing resolver fold, and removes only M184 from the
  deferred set.

## Constraints

- The resolver must consume `attribution_entity_socios.{n}.*` profile facts and
  must not invent missing values. A socio without an explicit
  `base_imponible_assigned` emits a source diagnostic and is not materialised
  as a zero row.
- `resolve_atribucion_binding_row_values` remains the canonical row fold and
  ordering authority. The application resolver adapts profile facts into
  `AtributionMemberObservation` and lets the registry helper produce
  row-indexed binding values.
- The promoted source kind leaves `DEFERRED_SOURCE_KINDS` and enters the live
  enrolled source set. Related-party and refund detail-row sources remain
  deferred under their existing governance.
- The new profile fact is a current schema field, not a migration or legacy
  compatibility branch.

## Implementation

The user-profile schema gains `attribution_entity_socios.base_imponible_assigned`,
a required money field on each repeatable socio row. The calculate mesh gains an
`AtribucionMemberSourceResolver` that loads the active profile, groups indexed
`attribution_entity_socios.{n}.*` facts, validates that each row has NIF, name,
share percentage, and assigned base, then constructs the existing typed
`AtributionMemberObservation` rows. It passes those observations to
`resolve_atribucion_binding_row_values`, carries the resulting row binding
values on `CalculationSourceResolution.row_binding_values`, and persists
matching `Modelo184MemberRow` detail rows for replay and rendering. Incomplete
rows emit `source_issue` diagnostics rather than a row with a fabricated zero.

## Rationale

Option C is the smallest implementation that satisfies the deferral governance
and the S307 filing need. It keeps every concept on its existing owner: profile
schema owns durable socio facts, application aggregation owns source-mesh
resolution, and the registry detail-record helper owns row ordering and binding
projection. Explicit assigned base is necessary because M184 reports an amount,
not just a participation ratio.

## Consequences

- M184 attribution-member bindings no longer produce an unhandled-source
  advisory when the profile carries complete socio rows.
- Sociedad civil and comunidad de bienes profiles can calculate M184 member
  rows from durable profile facts, while the existing manual `--row miembro`
  path still remains available for operator-supplied rows.
- Profiles that only declare shares remain incomplete for M184 row production;
  this is deliberate and visible through source diagnostics.
- The source-kind disposition tests must now treat `atribucion_member` as
  enrolled, not deferred. The other informativa detail-row deferrals are
  unchanged.
