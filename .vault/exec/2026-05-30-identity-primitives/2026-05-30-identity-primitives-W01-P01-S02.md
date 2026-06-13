---
step_id: S02
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W01.P01.S02 — re-export BucketId from core.identity

## Scope

Re-export `BucketId` through the `aeat.core.identity` package `__init__`
so downstream consumers import via the package surface rather than the
private module path, per identity-primitives ADR Rule 4.

## Outcome

`src/aeat/core/identity/__init__.py` adds `from ._bucket import BucketId`
and includes `BucketId` in `__all__`.

## Verification

`from aeat.core.identity import BucketId` resolves cleanly.

## Commit

`b69a1aa4d` — feat(core/identity): re-export BucketId through package __all__
