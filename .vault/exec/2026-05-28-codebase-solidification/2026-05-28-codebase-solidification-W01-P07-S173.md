---
step_id: S173
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S173 — OracleEnvironment StrEnum promotion

## Outcome

Replaced `OracleEnvironment = Literal["production", "test_environment", "both"]`
with `class OracleEnvironment(StrEnum)` declaring `PRODUCTION`, `TEST_ENVIRONMENT`,
and `BOTH` members in `src/aeat/domain/calculations/registry/_live_parity.py`.
Added `from enum import StrEnum` import; retained `Literal` import for
`ParityVerdict`, `OracleSurfaceKind`, and other remaining Literal aliases.

Replaced all six default-value sites with enum members:
- `LiveParityCatalogue.lookup` signature default
- `resolve_cross_reference_oracle` parameter default (line ~447)
- `audit_oracle_bindings` parameter default (line ~494)
- `audit_registry_oracle_bindings` parameter default (line ~778)
- `_aeat_nif_iva_oracle.register_default` parameter default
- `_groi_oracle.register_default` parameter default

## Files touched

- `src/aeat/domain/calculations/registry/_live_parity.py`
- `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`
- `src/aeat/domain/calculations/registry/_groi_oracle.py`

## Verification

77 tests pass. Commit: 2f51c3e0d. `vault plan step check S173` applied.
