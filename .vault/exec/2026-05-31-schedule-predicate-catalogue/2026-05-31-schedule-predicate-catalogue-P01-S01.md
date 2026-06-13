---
tags:
  - '#exec'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S01'
related:
  - "[[2026-05-31-schedule-predicate-catalogue-plan]]"
---

# `schedule-predicate-catalogue` `P01.S01`

Eager `validate_registry()` call added inside `_load_authority` immediately after
the `ValidatedRegistryAuthority` dataclass is constructed. The LRU cache ensures
this fires once per process per registry fingerprint.

- Modified: `src/aeat/domain/calculations/registry/_authority.py`
- Modified: `src/aeat/domain/calculations/registry/test_authority.py`

## Description

Added `authority.validate_registry()` on line 167 of `_authority.py`, after the
dataclass constructor returns. The cache invalidation test was updated to use a
minimally-valid synthetic registry (with a self-contained legal/sources catalogue,
a corpus file whose sha256 matches the declared value, a single informational
casilla, a workbook parity ref, and a filing application link) so it continues to
pass through the new eager validation gate.

## Tests

- `test_authority.py`: 6 passed
- `test_registry_contract.py`: 4 passed
- Total: 10 passed, 0 failed
- Commit: 0c34aa736
