---
step_id: S112
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P33.S112 step record

## Step

Run final structural verification: pytest diagnostics suite, rg for cross-layer import
violations (adapters importing application, application importing adapters, domain importing
core as outbound), document actual counts.

## Verification results

### Diagnostics test suite

`pytest src/aeat/diagnostics/ -q` — 31 passed, 2 failed.

The 2 failures (`test_profile_get_rejects_unknown_profile_key_with_localized_boundary`,
`test_profile_get_rejects_blank_profile_option_before_storage_lookup`) are pre-existing
environment failures requiring a live active bucket session. They originate from commit
`f71428dd0` (prior campaign) and are not caused by any W13 change.

Identity placement suite: `pytest src/aeat/diagnostics/test_identity_primitive_placement.py`
— **21 passed** (includes the protect-list public-surface pin test).

### Cross-layer import violations (production code only)

All counts exclude `test_*.py` files.

| Direction | Count |
|---|---|
| `application/` importing `aeat.adapters` | 0 |
| `adapters/` importing `aeat.application` | 0 |
| `core/` importing `aeat.domain` | 0 |

Zero production cross-layer violations. Integration tests legitimately import adapters
(33 test files); this is expected behaviour.

### STRICT_FROZEN migration completeness

`rg "ConfigDict\(strict=True, frozen=True, extra=" src/aeat/ --glob "!test_*"` — 2 remaining
sites (the 2 documented bespoke exclusions: `storage/bucket/_layout.py` adds
`arbitrary_types_allowed=True`; `secure_objects.py` is excluded by documented rationale).
All 84 migrated files import `STRICT_FROZEN_CONFIG` from `core._models`.

## W13 wave summary

All 10 Steps (S103-S112) closed. The honesty-review wave resolved:
- CTIMEX-003 (production ImportError — filing/__init__.py)
- MERGE-014 (84-site STRICT_FROZEN migration)
- PROMOTE-001 protect-list (52 sites with constraint-shape rationale)
- W11 gate re-assertion (21 tests passing)
- MERGE-002 CalendarCCAA wontfix (ADR Rule 7 amendment)
- MERGE-013 IVA wontfix (ADR Consequences amendment)
- MERGE-003 ProfileFactValue → UserProfileFactValue rename
- AUDITPIPE-008 substitutability pre-filter (audit rule mandate)
- FOLLOWUP-007 deferred-tasks vault cross-references (tasks 583-587)
- Final structural verification (this step)
