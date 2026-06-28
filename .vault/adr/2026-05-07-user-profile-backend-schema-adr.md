---
tags:
  - '#adr'
  - '#user-profile-backend-schema'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-user-profile-schema-research]]"
  - "[[2026-05-07-user-profile-registry-dependencies-reference]]"
  - "[[2026-05-07-user-profile-deadline-dependencies-reference]]"
  - "[[2026-05-07-user-profile-renta-dependencies-reference]]"
  - "[[2026-05-07-user-profile-census-business-dependencies-reference]]"
  - '[[2026-06-04-user-profile-backend-schema-research]]'
---



# `user-profile-backend-schema` adr: `User Profile Backend Schema And Persistence` | (**status:** `accepted`)

## Problem Statement

The project needs a centralized user profile backend that is derived from
modelo calculation, filing, schedule, census, Renta, inmueble, IVA, and
category requirements. Current profile state is fragmented across scalar
profile keys, setup `AutonomoProfile` persistence, CLI `ProfileRecord` values,
tax-residence storage, Renta family models, usage-ratio storage, and
profile-adjacent ledgers.

The new backend must be explicit and schema-oriented while storing live user
information only in the secure DB backend. The implementation must be a clean
replacement, not a compatibility layer over the current fragmented surfaces.

## Considerations

The research establishes that profile information is already a registry input:
schedule predicates, Modelo 100 profile bindings, filing export headers,
deadline applicability, category usage ratios, IVA classification, and Renta
WEB Open projections all require profile facts.

The schema must be model-aware and period-aware. It must know which facts are
needed for a selected modelo, revision, filing year, and period.

The schema must distinguish operator profile facts from transaction/customer
facts. IVA classification needs operator-side regime/enrollment facts, but
transaction and counterparty facts remain transaction data.

The schema must distinguish schema metadata from live values. TOML stores
sections, field definitions, selector mappings, validation rules, and
model/revision requirements. Secure DB stores live values and immutable
snapshots.

The existing secure-object backend already supports encrypted payloads, hashed
lookup keys, sensitivity classes, and schema-version gates.

## Constraints

No legacy runtime support is permitted. Existing `PROFILE_KEYS`,
`AutonomoProfile` profile storage, tax-residence profile storage, usage-ratio
root storage, untyped CLI profile dictionaries, profile path checks, and alias
maps are replacement targets.

No live profile values may be stored in TOML, registry files, plaintext profile
files, or setup outputs.

Tests must exercise real behavior and must not rely on tautological assertions,
mocks, stubs, skips, xfails, monkeypatches, or fake shortcuts.

Shared-codebase safety is part of the architecture process. Implementation
work must avoid destructive git operations and must protect unrelated edits by
other team members.

## Implementation

Create a centralized TOML schema at `registry/aeat/user_profile/schema.toml`.
The schema is the authority for profile sections, canonical keys, field types,
required and conditional requirements, effective-date semantics, validation
constraints, registry selector projections, export-context projections,
snapshot requirements, and model/revision requirement groups.

Create a domain package for typed profile schema and value models. The domain
layer enforces the TOML-declared rules for canonical key parsing, type
validation, effective-period selection, model/revision preflight, profile
snapshot creation, export/import validation, and projections for registry,
deadlines, filing/export, Renta, rental, category usage ratios, and IVA
context. The domain package is not a second schema authority.

Create an application API for profile lifecycle operations: add, remove, edit,
list, read, duplicate, export, import, validate, and model/revision preflight.
All write operations go through schema validation and secure-object
persistence.

`remove` means a secure tombstone of the live profile root: the profile becomes
unselectable for new calculations, config reads, deadline preflight, and export
preflight. Immutable filing/export snapshots remain retained by snapshot ID and
hash for auditability and referential integrity. Normal profile removal is not
a hard purge of historical filing evidence. Portable exports are generated only
as user-directed output and are not retained by the backend as live state.

Persist live profile values and immutable snapshots through the secure DB
backend. The storage topology is classification-aware: the implementation may
use one encrypted aggregate object plus secure child records for high-cardinality
or higher-sensitivity sections, but all records are addressed through the
central profile API and profile identity.

Replace current profile consumers incrementally by boundary, but without
compatibility adapters: registry validation, deadline calendar, filing/export,
setup/config flows, Renta profile bindings, rental/inmueble projections, usage
ratios, and VAT context each move to canonical profile projections. Once a
boundary is converted, the old local profile surface is removed or made
unreachable in the same owned slice. No new code may read old profile roots,
aliases, plaintext profile files, or setup handlers as compatibility fallbacks.

Add profile snapshot and stale-check support for filing/review/export. The
canonical policy is an immutable secure DB profile snapshot plus deterministic
canonical hash. Drafts store `profile_snapshot_id`, `profile_snapshot_hash`,
and the profile schema version. Review, verify, and export read profile-derived
facts from that immutable snapshot, not from mutable live profile values. If the
current live profile projection for the same modelo/revision/year/period hashes
differently from the draft snapshot, review and export report the draft as
profile-stale and require recalculation or an explicit new draft.

## Rationale

This ADR accepts the research Option A: central TOML schema plus secure DB
value documents and snapshots.

This option best fits the approved direction because it makes the profile an
explicit schema construct, keeps sensitive live information in secure storage,
and creates one read/write API for CLI, Python, registry, deadlines, filing,
Renta, rental, usage-ratio, and VAT consumers.

The alternative of deriving a schema only from per-modelo selectors would make
profile UX and CLI key discovery too opaque. The alternative of making Python
the primary schema authority would weaken the requested TOML-oriented contract.

## Consequences

The initial schema will be large because it must cover identity, contact,
tax residence, census/enrollment, activities, IRPF/withholding, IVA,
filing/export context, Renta taxpayer/spouse/family, properties/rental, usage
ratios, and provenance/effective dating.

Registry validation will gain a dependency on the user-profile schema. This is
intentional: unknown profile selectors should fail during registry validation,
not during runtime schedule or export evaluation.

The secure storage model must decide how to split identity/census, financial,
usage-ratio, and high-cardinality rental/property facts by sensitivity and
storage shape before implementation writes production profile values. That
split must remain hidden behind the central API and must be recorded as part of
the Wave 2 execution evidence.

Existing tests and CLI flows must be rewritten to use typed profile APIs and
real secure DB behavior.

The plan that follows this ADR and the CLI ADR is allowed to continue beyond
initial feature completion through autonomous audit, review, and hardening
loops until no actionable profile-surface findings remain.
