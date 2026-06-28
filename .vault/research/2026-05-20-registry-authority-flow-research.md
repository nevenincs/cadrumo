---
tags:
  - '#research'
  - '#registry-authority-flow'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-modelo-registry-fragment-architecture-research]]"
---



# `registry-authority-flow` research: registry compilation and authority pipeline

This research captures the current registry orchestration flow and the
implementation risks found while reviewing the M200 fragment hardening work.
It extends the fragment-architecture research from physical TOML reviewability
into the production boundary that should serve compiled registry data to
application and adapter consumers.

## Findings

### Current flow

The current registry flow is best described as a deterministic compilation and
authority pipeline:

```text
TOML authoring tree
  -> loader/compiler
  -> strict schema objects
  -> registry validation
  -> validated authority
  -> selected snapshot
  -> projection/runtime consumers
```

The authoring layer is the fragmented TOML tree under
`src/aeat/_data/registry/...`. It is optimized for legal-data review and should
not leak into runtime consumers.

The compiler layer lives in `_loader.py`. It supports single-file modelos,
directory-mode modelos, and revision fragment directories. It merges fragments
into raw revision payloads and then validates those payloads into strict
`ModeloDefinition` and `ModeloRevision` objects.

The validation layer lives in `_validate.py` and the pydantic schema models.
It validates the merged object graph rather than the authoring layout:
reference closure, duplicate primary ids, legal/source coverage, export layout
consistency, relation/binding/formula wiring, and related invariants.

The authority layer is `ValidatedRegistryAuthority`. It is the intended
production abstraction for compiled registry access: loaded modelos,
catalogues, validation state, deadline windows, and snapshot caching.

The snapshot layer selects one revision for a filing context and materializes a
`RegistrySnapshot`. Runtime consumers should depend on snapshots or typed
projections derived from snapshots rather than raw loaders, fragment paths, or
partially merged dictionaries.

### Current inconsistency

The abstraction exists but is not fully enforced. Some production code uses
`ValidatedRegistryAuthority`; other code still calls `load_registry_tree`
directly and then performs local orchestration. This creates multiple
registry-entry paths with different cache boundaries and makes it easy for a
caller to bypass future authority-level invariants.

One concrete risk is already visible. The filing runtime computes a complete
registry tree fingerprint before building its schema provider, but it then
asks `ValidatedRegistryAuthority.load` for an authority. The authority cache is
currently keyed only by `root` and `source_root`, so the higher-level
fingerprint can miss while the authority still returns stale data for the same
paths. This violates the fragment architecture requirement that every read
TOML file participate in cache invalidation.

Another concrete risk appears after same-record export fragments were enabled.
The loader appends nested `fields` arrays for repeated record ids, but the
validator collapses export field ids into a set for reference checks. Duplicate
field ids can therefore survive in a merged record and make export references
ambiguous.

### Desired abstraction

The production abstraction should be:

```text
RegistryAuthority = compiled registry + catalogues + validator + snapshot factory
```

The loader remains a compiler implementation detail. It owns deterministic
TOML discovery, merge order, scalar conflict rejection, local-catalogue
rejection, schema materialization, and cache fingerprints for the files it
reads.

The authority is the only production orchestration boundary. Application code,
CLI surfaces, query services, filing schema providers, export adapters, and
calculation orchestration should request validated modelos or snapshots from
the authority or from a repository facade that owns an authority.

Snapshot construction should remain authority-owned. Consumers may project
snapshots into their local view models, but they should not select revisions or
re-run registry validation independently.

### Rollout implications

The codebase is large enough that enforcement must be monotonous and staged.
The rollout should first fix the authority cache contract and nested export
field identity, then inventory all `load_registry_tree` call sites, classify
test-only versus production use, and migrate production call sites behind
`ValidatedRegistryAuthority`.

After migration, tests should enforce that production modules do not import raw
registry loaders except in the authority/compiler boundary. Existing tests may
continue to exercise raw loader behavior directly because they guard the
compiler itself.

The plan must include package hygiene separately from semantics. Registry-wide
pytest currently exceeds a ten-minute run in this environment, and
registry-wide ruff is blocked by existing import-order issues. Those gates
need either cleanup or explicit scoped substitutes during the rollout.
