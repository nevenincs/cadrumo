---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6982d59a0f51dcd4632e0b4c5a8febc3928ab5ed439819981f3cc57532f05997'
step_id: 'S22'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Remove the container-daemon prerequisite from the prove legs

## Scope

- `dev/packaging/smoke_docker.py`

## Changes

M dev/packaging/campaign.py
M dev/packaging/tests/test_campaign.py

## Notes

Both lanes that carried a container form lose it, and every profile that selected one
drops the entry. No prove leg now requires a reachable container daemon, so the same
lane set runs on each declared target rather than passing on some and being
unschedulable on others.
