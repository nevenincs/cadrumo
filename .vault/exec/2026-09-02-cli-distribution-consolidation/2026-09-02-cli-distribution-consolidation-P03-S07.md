---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1a6ec6edde5d93246c3f5450af05f2621559b80a01a9d058d0710fabe6675460'
step_id: 'S07'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Add the distribution smoke check asserting both console scripts

## Scope

- `dev/smoke/smoke_check.py`

## Changes

A dev/smoke/smoke_check.py

## Notes

The check ships asserting metadata, import, the version report and the root command
families. The MCP console script and the headless full-screen start are not asserted
yet: neither exists until the harness merges into the wheel and the root option is
routed. Both assertions are carried by the Steps that create the surfaces they test.
