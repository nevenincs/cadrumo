---
tags:
  - '#exec'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-submit-safety-sweep-plan]]'
---

# `live-submit-safety-sweep` `phase-1` summary

Completed the live-submit safety sweep by replacing the stale
override-confirmation contract with explicit execution mode, a distinct
live-submit env gate, internal confirmation, append-only audit logging,
and CLI refusal of unsupported live paths.

- Modified: `src/aeat/submission/_engine.py`
- Modified: `src/aeat/workflow/_engine.py`
- Modified: `src/aeat/cli/submission/submit.py`
- Modified: `src/aeat/cli/filing/__init__.py`
- Created: `src/aeat/submission/_audit.py`
- Created: `src/aeat/submission/_confirm.py`
- Created: `src/aeat/cli/submission/audit_log.py`

## Description

The implementation moved live-write authority into the submission
engine. Live submission now requires explicit `dry_run=False`, refuses
under pytest, requires `AEAT_LIVE_SUBMIT_ENABLED`, passes through the
internal exact-phrase confirmation hook, and records append-only audit
events. Workflow and CLI surfaces were migrated to explicit
`--dry-run` or `--live` selection, and `_NullSession`-backed submit
commands now fail closed instead of reporting fake live success.

## Tests

Focused verification passed on the affected surfaces:

- `uv run pytest src/aeat/submission/test_engine.py src/aeat/submission/test_confirm.py src/aeat/submission/test_live_submission.py -q`
- `uv run pytest src/aeat/cli/submission/test_cli.py src/aeat/cli/filing/test_filing_cli.py src/aeat/filing/test_live_complementaria.py src/aeat/cli/workflow/test_cli.py src/aeat/workflow/test_engine.py tests/test_config.py -q`
