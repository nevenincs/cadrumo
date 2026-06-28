---
step_id: S37
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P12.S37 — STRICT_FROZEN pre-condition audit (MERGE-014)

## Outcome

The plan states "audit all 10 _STRICT_FROZEN declarations". Actual count via ripgrep over production (non-test) files: approximately 90 modules declare `_STRICT_FROZEN = ConfigDict(...)`. The action tracker's "10" was a severe undercount.

## Diverging declarations (must stay module-local)

Two modules declare `_STRICT_FROZEN` with `arbitrary_types_allowed=True`:

- `adapters/persistence/storage/bucket/_layout.py:31` — `ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)` — needed for `BucketPaths` which holds `Path` objects (not pydantic-coercible by default)
- `adapters/persistence/storage/sql/secure_objects.py:36` — `ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)` — needed for SQLAlchemy ORM-mapped types

One existing canonical already in `core/`:

- `core/json_contract.py:31` — `_STRICT_FROZEN_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True, validate_assignment=True)` — diverges with `validate_assignment=True`; this is intentional for mutable JSON contract models and must NOT consume the shared constant.

## Standard declarations (safe to migrate)

All remaining ~87 modules use `ConfigDict(strict=True, frozen=True, extra="forbid")` — identical to the canonical. Migration is safe.

## Decision

- The two `arbitrary_types_allowed=True` modules keep their local `_STRICT_FROZEN`.
- `core/json_contract.py`'s `_STRICT_FROZEN_CONFIG` keeps its `validate_assignment=True` variant.
- All other modules with the standard 3-key config can migrate to `STRICT_FROZEN_CONFIG` from `core._models`.
- S38 and S39 execute the first 10 migrations; the remaining ~80 are follow-up work beyond the 10-module plan scope.

## Files touched

None (audit step).
