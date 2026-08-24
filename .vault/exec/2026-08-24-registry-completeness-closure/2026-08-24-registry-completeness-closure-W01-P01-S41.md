---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c9d93d5ff2202deea508f52933ca7774fdd1b7532043a1cdbe887c88e83cdeb4'
step_id: 'S41'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Align the authority snapshot cache-key type with its grade-separated runtime key

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`

## Description

- Align `_SnapshotKey` with the six values stored by `ValidatedRegistryAuthority.snapshot`.
- Retain the requested `RegistryAuthorityGrade` as the final cache-key element.

## Outcome

The static cache-key contract now matches the established runtime key. Snapshot caching and authority-grade separation are unchanged.

## Notes

Focused Ruff and snapshot-grade enforcement tests pass. BasedPyright reports the pre-existing private import of `_build_validated_snapshot` in `_authority.py`; this Step does not alter that import or suppress the diagnostic.
