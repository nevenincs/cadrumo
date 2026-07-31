---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:5530243105c442657e0295ddcfbede308ec26e959e94cc5158aef1ebf38b294d'
step_id: 'S13'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# real-CLI tests asserting each ledger verb surfaces specific field error not generic boundary

## Scope

- `src/aeat/entrypoints/cli/test_ledger_validation_paths.py`

## Description

- Reconciled the historical validation-path test work to the Wave-1 commit review.
- Confirmed `650cb762c` provides the reviewed regression coverage.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the test coverage. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S16; each row receives its own record.
