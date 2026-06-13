---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S38'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `schema-hardening` `W04.P08.S38` step record

Scope: `W04.P08.S38` - Audit validator module reviewability baseline failure.

## Description

- Measure validator module sizes.
- Run the validator-module reviewability test.
- Record the failing module, current measured line count, and baseline.
- Keep the repair scoped to reducing module size rather than raising the baseline.

## Outcome

The validator reviewability gate fails only for `_validate_relation_periods.py`, reported by the test at 240 lines against the 203-line baseline.

## Notes

This is an audit-only step. The next step owns the behavior-preserving size reduction.
