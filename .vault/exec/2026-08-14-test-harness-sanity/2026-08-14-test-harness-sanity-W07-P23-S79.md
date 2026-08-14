---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:9874b2e3f819ddc5904ba6902ba27e9002555f47690f38df7a105f73af07c41c'
step_id: 'S79'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Restore the no-monkeypatch gate and discriminating controls to green

## Scope

- `src/cadrumo/tests/test_monkeypatch_inventory.py`

## Description

- Run the live no-monkeypatch inventory against the complete discovered test-control population.
- Run every parametrized forbidden-shape positive control through the same policy path.
- Require discovery non-vacuity and exact finding counters.

## Outcome

The repository no-monkeypatch gate is green after S75-S78. The exact nine-item selection covers the live inventory, seven discriminating mutation/import/alias/context controls, and the shared discovery non-vacuity guard; no test-file edit was required.

## Notes

The exact configured selection passed 9 tests in 35.55 seconds across 3,294 discovered test-control modules. Collect-only confirmed all nine expected items and no omitted positive control. Independent review verified exact `Counter` assertions detect both missed and spurious findings. This is focused S79 evidence only, not a claim that broader campaign gates are green.
