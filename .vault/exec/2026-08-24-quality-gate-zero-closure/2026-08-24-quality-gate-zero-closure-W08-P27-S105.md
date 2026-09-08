---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b3722bff42c8c765422f6c3da2db102f0613c167f4c545f8b0a335ab67508dcc'
step_id: 'S105'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# Run mutmut against one bounded package and record wall clock, mutant count, killed and surviving counts, establishing this suite's real cost per package rather than an assumed one (Luna max audit and mechanical)

## Scope

- `.vault/audit/`

## Changes

- `A` `.vault/audit/2026-09-07-quality-gate-zero-closure-bounded-mutmut-measurement-audit.md`
- `verify:` `UV_PROJECT_ENVIRONMENT=/tmp/cadrumo-s105-env-wsl uv run --frozen mutmut run "dev.quality.tautological_assertion_scan*"` -> `pass`
