---
step_id: S40
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S40 — NamespaceRegistryError test coverage

## Outcome

Extended `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
with 16 new real-behavior tests. Tests assert: `INTEGRITY_STORAGE_NAMESPACE_REGISTRY`
is present in `ERROR_REGISTRY`; `build_error_envelope` round-trips with
correct code and category; each of the 13 replaced invariant paths raises
`NamespaceRegistryError` via the production validator with real invalid input
(namespace key whitespace, key path separators, namespace slug separators and
whitespace, default_object_key path separators and whitespace, path key
whitespace and separators, path segment whitespace and separators, duplicate
namespace keys, duplicate namespace values, duplicate path keys).

## Files touched

- `src/aeat/adapters/persistence/storage/test_namespace_registry.py`

## Verification

`uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_namespace_registry.py -xvs` — 25 passed (16 new, 9 pre-existing).
