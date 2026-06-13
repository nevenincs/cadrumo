---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S39'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `schema-hardening` `W04.P08.S39` step record

Scope: `W04.P08.S39` - Reduce relation-period validator module below its reviewability baseline.

## Description

- Shorten accumulated explanatory docstrings and comments in `_validate_relation_periods.py`.
- Keep relation selector, period-overlap, and source-year coverage logic unchanged.
- Tighten trivial helper bodies without changing their return contracts.
- Preserve the existing 203-line reviewability baseline instead of raising it.

## Outcome

`_validate_relation_periods.py` now has 203 `splitlines()` lines and passes the validator-module reviewability gate.

## Notes

Verification passed: ruff on touched registry files, full `test_registry_reviewability.py`, and `test_committed_registry.py`.
