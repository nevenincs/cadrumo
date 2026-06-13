---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S72'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P19.S72`

Scope: `justfile`.

## Description

- Added `audit-complexity-tests` as the top-level package ratchet-test
  complexity lane.
- Scoped the lane to `src/aeat/test_*.py` so it tracks inventory and closure
  tests separately from production source.
- Used the same programmatic Complexipy approach as the production lane so the
  file cohort is explicit and portable across Windows and Unix recipes.
- Preserved failing exit-code behavior while findings exceed the cognitive
  threshold.

## Outcome

S72 is closed. Production and top-level ratchet-test complexity now have
separate `just` endpoints and can be triaged independently.

## Notes

Verification:

- `uv run --no-sync vaultspec-rag search "top-level package test complexity ratchet audit-complexity-tests justfile complexipy" --type code --max-results 8 --port 8766 --json`
- `fd "test_.*\\.py" src/aeat -d 1`
- `just --list`
- `just audit-complexity-tests`

Current top-level ratchet-test cognitive leaders:

- 50: `src/aeat/test_utc_validator_enrollment_inventory.py::_file_has_inline_tzinfo_guard`
- 30: `src/aeat/test_canonical_clock_usage.py::_collect_violations`
- 27: `src/aeat/test_mock_inventory.py::_mock_imports`
- 24: `src/aeat/test_core_time_deletion_and_cast_rationale.py::_collect_cast_violations`
- 24: `src/aeat/test_cast_rationale_inventory.py::_collect_violations`
