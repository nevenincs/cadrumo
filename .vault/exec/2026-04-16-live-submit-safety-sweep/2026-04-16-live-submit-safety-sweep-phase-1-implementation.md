---
tags:
  - '#exec'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-submit-safety-sweep-plan]]'
---

# `live-submit-safety-sweep` `phase-1` `implementation`

Implemented the production safety-contract migration for issues `#142`
through `#146`.

- Modified: `src/aeat/config.py`
- Modified: `env/.env.example`
- Modified: `src/aeat/workflow/_protocols.py`
- Created: `src/aeat/submission/test_confirm.py`

## Description

The changed code removes the legacy `override_confirmation` and
`AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` path, introduces
`AEAT_LIVE_SUBMIT_ENABLED`, adds `_confirm.py` and `_audit.py`, makes
submission and workflow APIs require explicit `dry_run`, and adds
`aeat submission audit-log`. The amendment and workflow CLIs were
aligned to the same explicit mode-selection contract.

## Tests

The focused submission, CLI, workflow, and config slices passed locally
after the contract migration. The live-marked amendment and submission
coverage remains dry-run only, preserving the no-live-write test
boundary.
