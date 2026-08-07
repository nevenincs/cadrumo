---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority flow

Treat the modelo registry as a deterministic authoring-compiler pipeline:
TOML authoring tree → loader/compiler → strict schema objects → registry
validation → validated authority → immutable snapshots → runtime projections.

**`ValidatedRegistryAuthority` is the production orchestration boundary.**
Request validated modelos, deadline windows, and snapshots through the authority
or a repository facade that owns one. Do not add production paths that call raw
loaders and then independently validate or select revisions.

**`_loader.py` is a compiler implementation detail.** Loader changes MUST
preserve deterministic merge order, reject ambiguous scalar conflicts, include
every read TOML file in cache invalidation, and compile fragments into the
existing strict runtime schema.

**Snapshot construction is authority-owned.** Filing schema providers, query
services, formula execution, export parsing and adapter projections consume
`RegistrySnapshot` or typed projections derived from snapshots — never fragment
paths or partially merged raw dictionaries.

**Invalidate any cache above the loader by the complete registry tree
fingerprint**, including directory-mode manifests and recursive revision
fragments. Never introduce a path-only registry cache that can serve stale TOML.

## Revision content is fragmented

A revision declares its sections — bindings, formulas, casillas, verification
expectations and predicates, constructs, completeness manifest — ONLY in
fragmented subdirectories. The fragment directory's `revision.toml` carries
scalar metadata only, and an inline section table is a hard `RegistryLoadError`.

**Assess coverage from the LOADED snapshot, never a directory listing.** To
decide whether a revision is calc-grade or a casilla is ledger-bound, load
through the authority and inspect the compiled schema; grep fragments only to
pin exact ids. A file-shape glob undercounts the same way — a pattern matching
one shape silently excludes directory-mode fragments, which can hold most of the
corpus. Assume fragmentation until you have checked; both shapes ship.

Read a binding's `source` field before classifying a blank: a `profile` binding
absent from a ledger sweep is not a ledger silent-zero.

Source: ADR `2026-07-02-arch-remediation-registry-format-adr`.
