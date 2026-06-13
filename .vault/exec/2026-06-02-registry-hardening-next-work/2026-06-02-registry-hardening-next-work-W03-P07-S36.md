---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S36'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `schema-hardening` `W03.P07.S36` step record

Scope: `W03.P07.S36` - Tighten committed registry TOML file-size and row-width regression gates.

## Description

- Make the TOML reviewability scan explicitly target committed modelo registry fragments.
- Tighten the file hard cap from 5,000 lines to 1,500 lines.
- Tighten the row-width hard cap from 1,200 characters to 600 characters.
- Tighten the baseline assertions to 1,250 lines and 575 characters.

## Outcome

The committed modelo registry corpus is now guarded by post-fragmentation size and row-width thresholds that match the S35 measurements.

## Notes

Verification passed for the focused TOML reviewability tests and ruff on the touched test file. A full-file run also surfaced an unrelated validator-module baseline failure for `_validate_relation_periods.py`, which remains to be tracked as validator decomposition work.
