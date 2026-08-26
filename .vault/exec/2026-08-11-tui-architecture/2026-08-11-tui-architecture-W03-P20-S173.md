---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:627840d2bb3b51a734a0e4ce2da92cffa242bb9767d8e162189d10ee5dadae82'
step_id: 'S173'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Semantically harden the already-public domain/calculations/registry/authority.py owner after c94133f29516b12e3529f3d154c31592562f6198 delivered the mechanical private-to-public relocation, direct-import and API-documentation cutover, and inert registry package, consume the reviewed S175 matrix row for this family rather than replaying that move, generate and commit a schema-versioned deterministic authority consumer census whose check mode derives every definition and production, test, fixture, documentation, tooling, annotation, registration, dynamic-target, package-attribute, and transitive consumer instead of relying on unexplained fixed counts, replace the separate load-state-key and comparison-domain normalization paths with one canonical physical registry-root and source-root pair identity helper shared by both, resolve relative, dot-segment, and symlink aliases to one identity, apply platform-native case policy so case aliases coalesce only on case-insensitive filesystems and remain distinct on case-sensitive filesystems, fail closed on unresolvable roots, derive only the opaque ContentDigest domain from that pair plus a guarded process incarnation without exposing roots, PID, or nonce, preserve the native process-monotonic generation and domain-before-integer comparison, install an after-fork and PID guard that rekeys the child incarnation without acquiring inherited locks, reconstructs the state lock, load barrier, root load-state map, generation and reset state before a fresh child load, binds each authority instance to its creating PID and incarnation, and rejects every inherited parent capture or current-coordinate access, delete read_current_generation and every compatibility alias, and prove parent capture and current-coordinate exercise in the child, fork during active readers without deadlock, child re-key and inherited-instance refusal followed by a fresh child load, same-physical-root relative, dot, symlink, and platform-case aliases, distinct registry-root and source-root mismatches, same-domain reset succession, real A -> B -> A invalidation, cross-process refusal, deterministic census drift refusal, and zero ModeloWorkspace, shim, fallback, bridge, package binding, or re-export

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`
- `src/cadrumo/domain/calculations/registry/__init__.py inertness canary`
- `dev/quality/registry_authority_consumer_census.py`
- `dev/quality/registry_authority_consumer_census.v1.json`
- `dev/tests/test_registry_authority_consumer_census.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `and focused physical-root-alias/case/symlink/reset/ABA/process/fork/concurrency/current-coordinate/no-compatibility tests`

## Changes

- `M` `dev/quality/registry_authority_consumer_census.v1.json`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest dev/tests/test_registry_authority_consumer_census.py src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py src/cadrumo/domain/calculations/registry/tests/test_authority.py -n0` -> `pass`

## Notes

The authority hardening, fork guard, physical-root identity and
`read_current_generation` deletion landed under the two S173 remediation
audits; this record closes the Step by clearing its remaining S175 sequencing
gate and re-deriving the drifted consumer census. One fork proof is skipped on
this platform by a POSIX capability guard.
