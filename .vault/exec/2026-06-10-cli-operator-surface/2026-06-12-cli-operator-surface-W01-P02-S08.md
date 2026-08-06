---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:b988958ce67cbc9bc7c28a81b07fc11bb25e9667df01b2d893ca6f7d2fdf61ec'
step_id: 'S08'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W01.P02.S08 Preflight Default Tests

Scope: verify real behavior tests for natural-key preflight resolution and overrides.

## Description

- Ran tests proving preflight answers from modelo, filing year, and period without `--revision-id`.
- Ran tests proving explicit `--revision-id` remains honored.
- Ran tests proving unresolvable or ambiguous natural keys refuse with discovery/candidate guidance.

## Outcome

S08 is closed. The real-behavior test module covers natural-key defaulting, explicit override, and refusal guidance.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_config_preflight_revision_default.py`.
