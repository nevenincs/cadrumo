---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:494dfd8b24a04b5afe0f4eeb9613f367466e5f17ab17393a4bc780fc0dac5c9d'
step_id: 'S51'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---
# Rename advisory security wiring without presenting it as a blocking check

## Scope

- `dev/audit and dev/quality`

## Changes

- `M` `dev/audit/advisory.py`
- `M` `dev/audit/security.py`
- `M` `dev/quality/suite.py`
- `M` `dev/quality/tests/test_suite_gate_table.py`
