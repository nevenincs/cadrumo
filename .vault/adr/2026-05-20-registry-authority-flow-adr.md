---
tags:
  - '#adr'
  - '#registry-authority-flow'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-registry-authority-flow-research]]"
---



# `registry-authority-flow` adr: validated authority as the registry orchestration boundary | (**status:** `accepted`)

## Problem Statement

The modelo registry now has a reviewable fragmented authoring layout, but the
runtime orchestration boundary is still inconsistent. Some production paths use
`ValidatedRegistryAuthority`, while others call raw loaders and perform local
validation, revision selection, or projection work. That split creates duplicate
registry-entry paths, weakens cache invalidation, and makes it hard to enforce
future registry invariants across a large codebase.

The registry needs one explicit production abstraction that describes the whole
flow from compiled TOML to runtime consumers.

## Considerations

The fragment architecture ADR already established the authoring/runtime
separation: TOML fragments are source files, not runtime domain concepts. The
loader compiles fragments into the existing strict schema objects, and existing
validators consume the merged object graph.

The current implementation has a natural authority abstraction:
`ValidatedRegistryAuthority` owns loaded modelos, catalogues, validation state,
deadline-window access, and snapshot caching. `RegistrySnapshot` is already the
stable runtime slice for calculation, filing, query, export, and adapter
projections.

The codebase is large. A successful rollout must be organized, precise,
monotonous, persistent, and repetitive: inventory call sites, classify test-only
versus production usage, migrate one boundary at a time, add enforcement tests,
and keep verification scoped enough to run reliably.

Concrete review findings support the need for a single authority boundary:

- path-only authority caching can serve stale registry data after TOML changes;
- same-record export fragment merging can preserve duplicate nested field ids;
- package-wide registry gates are currently noisy or too slow for fast feedback.

## Constraints

Do not expose TOML fragments, raw dictionaries, or partially merged revisions to
application or adapter consumers.

Do not introduce a parallel runtime schema, compatibility shim, or duplicate
registry service. The accepted runtime objects remain `ModeloDefinition`,
`ModeloRevision`, `RegistryCatalogues`, and `RegistrySnapshot`.

Do not special-case current large modelos such as M200 or M100. Loader and
authority rules must remain generic across modelo ids and revision layouts.

Do not weaken legal/source grounding, strict validation, or existing pydantic
boundary models while migrating orchestration paths.

Tests must remain real-behavior tests. They may exercise raw loaders only when
testing compiler behavior directly; production orchestration tests should use
the authority boundary.

## Implementation

Adopt this registry flow as the canonical architecture:

```text
TOML authoring tree
  -> loader/compiler
  -> strict schema objects
  -> registry validation
  -> validated authority
  -> selected snapshot
  -> projection/runtime consumers
```

Define the production abstraction as:

```text
RegistryAuthority = compiled registry + catalogues + validator + snapshot factory
```

Keep `_loader.py` as the compiler implementation detail. It discovers TOML,
computes complete cache fingerprints, rejects local catalogues and scalar
conflicts, merges fragments deterministically, and materializes strict schema
objects.

Keep `ValidatedRegistryAuthority` as the only production orchestration boundary
for registry-backed modelo access. Production callers request modelos,
deadline windows, and snapshots through the authority or through repository
facades that own an authority.

Keep snapshot construction authority-owned. Runtime consumers may project a
`RegistrySnapshot` into local view models, but they do not independently select
revisions, re-run validation, or consume raw loader output.

Enforce the boundary in stages:

- fix authority cache invalidation so complete registry tree fingerprints reach
  every cache above the loader;
- add nested export-field duplicate detection for merged export records;
- inventory direct `load_registry_tree` imports and classify test-only versus
  production usage;
- migrate production call sites to `ValidatedRegistryAuthority`;
- add structural tests that reject new production imports of raw registry
  loaders outside compiler/authority boundaries;
- clean or scope package-wide registry gates so the rollout has reliable
  verification.

## Rationale

This option uses abstractions already present in the codebase instead of adding
a new service layer. It preserves the authoring/runtime separation established
by the fragment architecture while making the runtime side explicit and
enforceable.

A single authority boundary reduces stale-cache risk because cache invalidation
can be owned in one place. It also narrows validation responsibility:
validators remain object-graph validators, loaders remain compilers, and
consumers receive immutable snapshots rather than deciding how to compile,
validate, or select registry data.

The alternative, allowing production callers to keep using raw loaders, spreads
registry orchestration across application, adapter, query, and CLI code. That
is cheaper locally but expensive over time: every new invariant must be audited
against many entry paths.

## Consequences

Short term, this creates a migration backlog. Direct raw-loader call sites must
be inventoried and moved deliberately, with tests added as each production
surface is brought behind the authority.

Some tests will continue to call raw loaders. That is acceptable when the test
is specifically about loader/compiler behavior, but not when it is asserting
production orchestration.

The authority cache API likely needs a signature change or an internal
fingerprint dependency. That may affect repository facades and filing runtime
provider caches.

Registry-wide verification needs cleanup. Until package-wide ruff and full
registry pytest are practical gates, the rollout plan must use focused tests
plus explicit notes about residual package-wide risk.
