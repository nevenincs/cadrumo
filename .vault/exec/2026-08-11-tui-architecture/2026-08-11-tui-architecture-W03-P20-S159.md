---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:128ce95b3545f985e7c990282ae647bca41b3ea87337f1ba55cb528a65682006'
step_id: 'S159'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose through the canonical registry facade a registry-native atomic capture of the law-selected inspection or snapshot and its process-incarnation-local ABA-safe monotonic generation, plus current-generation validation, without any ModeloWorkspace dependency, alternate loader, private grammar, shim, alias, fallback, or re-export bridge

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`

## Description

- Grounded the sole registry capture surface in the accepted Workspace owner-seam ADR amendment, S126 contract, S128 composition reference, and the canonical registry authority before remediation. Vaultspec RAG reached the governing vault records; its running code index had not yet incorporated this current shared-worktree source, so the final semantic query was paired with an exact current-HEAD source census rather than treated as an absence proof.
- Replaced the identity-keyed LRU and detached failure cache with one root-and-source-root scoped current-authority slot. Identity collection, cached success or failure reuse, construction, and publication now share the slot's transition lock. Each observed identity change advances the native process-local generation before construction and clears the prior published authority, so a physical A to B to A tree cycle constructs a fresh later A incarnation rather than reviving the original object.
- Added a reset-aware reader/writer barrier: loads, native captures, and current-generation reads are readers; reset blocks new readers, drains existing ones, clears authority, loader, and fingerprint caches in one exclusive operation, and excludes concurrent reset writers. Per-authority validation and snapshot work retain only their own state locks, allowing unrelated roots to load independently.
- Kept the native snapshot cache as the sole snapshot authority but made it private. Public `snapshot` returns a deep isolated copy and native capture deep-copies the same private cache entry under the owner lock, preventing a caller-held mutable snapshot map from changing or tearing a captured projection.
- Retained the one public facade promotion from the earlier S159 source commit; no Workspace type, alternate loader, shim, alias, fallback, re-export bridge, or second capture home was added.

## Outcome

The registry owns one public native capture/current-generation surface. An unchanged cold identity has exactly one published authority and generation; every same-root observed transition, including restored A after B, makes prior authorities refuse and allocates a later generation. Reset cannot publish an in-flight pre-reset load after it completes, and concurrent reset writers cannot overlap. Public mutable snapshot copies cannot mutate the authority-private capture source. Independent review remains required before this Step may close.

## Verification

- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_authority.py src/cadrumo/domain/calculations/registry/tests/test_authority.py src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py` -- passed.
- `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/_authority.py src/cadrumo/domain/calculations/registry/tests/test_authority.py src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py` -- passed with zero errors and warnings.
- `uv run --no-sync pytest -q -o addopts= src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py` -- 9 passed.
- `uv run --no-sync pytest -q -o addopts= src/cadrumo/domain/calculations/registry/tests/test_authority.py` -- 10 passed.
- `uv run --no-sync pytest -q -o addopts= src/cadrumo/domain/calculations/registry/tests/test_authority_cache_key_digest.py src/cadrumo/domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py src/cadrumo/domain/calculations/registry/tests/test_validation_verdict_cache.py` -- 17 passed.
- Final exact census: one production definition of `RegistryAuthorityCapture`, one production `capture_law_selected_projection` and `read_current_generation` home in `_authority.py`, one canonical package-facade promotion, zero `ModeloWorkspace` or producer-contract references under the registry, and no legacy global capture lock, LRU authority cache, detached failure cache, or cache-clear alias.

## Notes

The shared worktree advanced while this Step was in progress. The original S159 source/facade implementation was swept into `8c845ab92f`; the remediation source and authority tests were swept into `d8d47ee410`. This executor preserves both current commits and does not amend or restage unrelated files. The Step is deliberately still open pending a fresh independent review that supersedes the earlier FAIL audit.
