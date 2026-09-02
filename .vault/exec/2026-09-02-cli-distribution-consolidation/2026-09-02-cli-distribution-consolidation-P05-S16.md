---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1806553b6ce3b18dfa472a96599028f904f14f264aa9f3fb855606e8a3cb4d59'
step_id: 'S16'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Declare the root command's full-screen capability

## Scope

- `src/cadrumo/entrypoints/cli/_root_command_specs.py`

## Changes

M src/cadrumo/entrypoints/cli/_root_command_specs.py
M src/cadrumo/entrypoints/cli/tests/test_global_tui_request.py

## Notes

The enrolment gate carried a hardcoded set of enrolled command keys that the new
declaration falsified, and a second gate asserted the bare root path refuses as
unimplemented. Both expectations were stale rather than wrong in kind: the root path
now refuses on console capability instead, which is what proves the request is routed.
