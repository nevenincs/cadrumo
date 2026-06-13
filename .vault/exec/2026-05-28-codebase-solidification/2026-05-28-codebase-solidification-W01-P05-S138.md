---
step_id: S138
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
  - "[[2026-05-28-codebase-solidification-W01-P05-S137]]"
---

# codebase-solidification W01.P05.S138 step record

## Step

Add real-behavior test asserting the coercion and the validation variants behave per their documented contracts on naive / aware / mixed inputs; `src/aeat/core/time/test_utc.py`.

## Outcome

Created `src/aeat/core/time/test_utc.py` with 10 parametrized, real-behavior test cases split across two test classes:

- `TestCoerceUtcAware`: 5 cases covering naive input (attaches UTC), UTC-aware passthrough, +02:00 and -05:00 offset conversion, and return-type assertion.
- `TestValidateUtcAware`: 5 cases covering UTC-aware passthrough, naive rejection (CoreValidationError), +02:00 and -05:00 rejection, and ValueError subclass inheritance verification.

Markers: `pytest.mark.unit`, `pytest.mark.domain_core`. No mocks, no skips, no xfail, no tautological assertions.

## Verification

- `uv run --no-sync pytest src/aeat/core/time/test_utc.py -xvs`: 10 passed in 0.16s.
- Commit: `2e0d737a2`
