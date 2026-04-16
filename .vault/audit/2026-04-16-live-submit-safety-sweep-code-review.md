---
tags:
  - '#audit'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-submit-safety-sweep-plan]]'
  - '[[2026-04-16-live-submit-safety-sweep-adr]]'
  - '[[2026-04-16-live-submit-safety-sweep-plan-review]]'
---

# `live-submit-safety-sweep` Code Review

REVIEW-001 | RESOLVED | Final audit record durability
The first review pass flagged that the final `DRY_RUN` or `LIVE_RESULT`
audit entry was appended after JSON persistence, which could lose the
only durable trail if persistence failed. The engine was amended so the
final append-only audit entry is written before `_persist(filing)`.

REVIEW-002 | RESOLVED | Live gate ordering before session creation
The first review pass flagged that a live attempt created a browser
session before the pytest/env/confirmation gates ran. The engine was
amended so `_guard_live_submission()` runs before any live-session
construction.

REVIEW-003 | RESOLVED | Missing amendment CLI `_NullSession` refusal coverage
The first review pass flagged that the complementaria CLI only tested
`--dry-run`. A unit test now covers the `--live` refusal branch and
asserts the `_NullSession` fail-closed behavior.

REVIEW-004 | INFO | Targeted verification passed
Focused verification passed after the review fixes:
`src/aeat/submission/test_engine.py`,
`src/aeat/submission/test_confirm.py`,
`src/aeat/cli/submission/test_cli.py`,
`src/aeat/cli/filing/test_filing_cli.py`,
`src/aeat/cli/workflow/test_cli.py`,
`src/aeat/workflow/test_engine.py`,
and `tests/test_config.py`.
