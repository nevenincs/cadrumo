---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S06'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Add one shared resolve_repository_bucket_id helper parameterised by error_type as the single explicit-or-active-bucket resolver

## Scope

- `src/aeat/core/identity/_bucket.py`

## Description

- Add `resolve_repository_bucket_id(bucket_id, *, error_type)` to
  `src/aeat/core/_bucket_pointer_io.py` (alongside `resolve_active_bucket_id`),
  carrying the shared `no_active_profile_bucket` message key and the blank /
  missing reason contexts.
- Type the error factory parameter as `type[AeatError]` via a `TYPE_CHECKING`
  import (annotation-only; no runtime import, no cycle), since the helper only
  constructs the passed-in `error_type`.
- Export the helper through `aeat.core` (`__init__` TYPE_CHECKING import block,
  `__all__`, and the lazy `__getattr__` allowlist).

## Outcome

Single canonical home for the explicit-or-active-bucket resolution now exists
in `core`. Import smoke-test green; ruff clean.

## Notes

The originating Step row guessed the scope path as
`src/aeat/core/identity/_bucket.py`; the correct home is
`src/aeat/core/_bucket_pointer_io.py` (it owns `resolve_active_bucket_id`, the
primitive this helper composes). Recorded here rather than rewriting the Step
row.
