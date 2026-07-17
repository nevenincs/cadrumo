---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Drive a real operator-persona CLI export then import recovery cycle and verify evidence bytes, audit trail, and cross-period calc inputs survive

## Scope

- `src/aeat/entrypoints/cli`

## Description

- Drive real export and import recovery through the CLI and application service tests.
- Verify evidence bytes, audit history, and calculation inputs survive recovery.
- Run the profile export/import CLI integration file after direct-source hardening.

## Outcome

- Complete. Focused recovery and CLI roundtrip gates passed.
- Verified by 59 focused custody/application tests and 6 CLI integration tests.

## Notes

- Full-tree vault check still reports unrelated historical feature-rename-integrity errors outside this feature.
