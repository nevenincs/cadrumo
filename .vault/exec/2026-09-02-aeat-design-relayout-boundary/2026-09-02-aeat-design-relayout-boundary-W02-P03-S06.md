---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:c0684ddbaf5a361f2a77d720e6e5cc1cbf8609f7647c8aee2d1c14175ee7c838'
step_id: 'S06'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Reject missing anchors, source drift, duplicate output, altered non-source payloads, and partial rebind application

## Scope

- `dev/registry/tests/test_m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run --no-sync python -m pytest -n 0 dev/registry/tests/test_m200_2024_full_reconciliation.py -q` -> `pass`
