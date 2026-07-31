---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:d569d85c8d5c08b07d3febc00f38d7cf676a8f0d1b36128c0f70d442e3563f3c'
step_id: 'S07'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W01.P02.S07 Preflight Natural-Key Default

Scope: reconcile the already-landed `config profile preflight` active-revision default.

## Description

- Verified `aeat config profile preflight --help` shows `--revision-id` as optional.
- Verified the help states the default is the active revision for modelo, filing year, and period.
- Ran the dedicated preflight revision-default test module.

## Outcome

S07 is closed. `config profile preflight` no longer requires an operator to supply an internal registry revision id for the common natural-key path.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_config_preflight_revision_default.py`.
