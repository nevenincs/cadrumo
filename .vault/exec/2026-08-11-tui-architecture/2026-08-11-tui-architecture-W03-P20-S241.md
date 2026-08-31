---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:57a190515c33a455ded952192a960fbf77d273b164c283ca8ea22511bce71a9f'
step_id: 'S241'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Privatize the snapshot implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/snapshot.py`

## Changes

A src/cadrumo/domain/calculations/registry/_snapshot_internals.py
M src/cadrumo/domain/calculations/registry/snapshot.py
M 6 in-package consumers repointed onto the private implementation
M dev/quality/registry_facade_family_census.v1.json

## Notes

Thirty-four construction, validation and cache symbols moved. snapshot.py keeps
build_snapshot and build_validated_snapshot, the two symbols callers outside the
package bind.

The row says privatise the IMPLEMENTATION, and that word settles what looked
like an open design question. The authority-owned rule governs production paths
and no production caller sits outside this package; the architecture rule says a
contract required outside its package -- counting test, fixture and tooling
consumers -- lives in a public defining module. So the contract stays public and
the machinery goes private.

The boundary was found by measuring, not by reading names. A first attempt kept
four symbols public and broke immediately: two of them are called BY the
internals and used only in-package.
