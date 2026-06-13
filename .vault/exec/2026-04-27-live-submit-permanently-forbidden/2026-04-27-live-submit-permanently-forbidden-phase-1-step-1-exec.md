---
tags:
  - '#exec'
  - '#live-submit-permanently-forbidden'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-live-submit-permanently-forbidden-plan]]'
---

# `live-submit-permanently-forbidden` `phase-1` `step-1`

Implemented the runtime excision and the first regression layer for the
permanent live-submit prohibition.

- Modified: `src/aeat/adapters/outbound/aeat/export/_engine.py`
- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py`
- Modified: `src/aeat/config.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/submission/__init__.py`
- Modified: `src/aeat/entrypoints/cli/workflow/run.py`
- Modified: `src/aeat/entrypoints/cli/workflow/next.py`
- Modified: `src/aeat/entrypoints/cli/doctor.py`
- Created: `src/aeat/adapters/outbound/aeat/export/test_live_submit_permanently_forbidden.py`

## Description

The engine no longer has a reachable live-submit transport. `dry_run=False`
now fails closed with `LiveSubmitForbiddenError`, and the historical
write-gate helper is reduced to a permanent-deny shim. Product configuration no
longer exposes live-submit env vars, and the amendment CLI no longer accepts a
live path. Older gate-preservation tests were replaced or removed in favor of
permanent-forbid assertions.

## Tests

Focused unit validation passed against the changed surfaces:

- `uv run pytest src/aeat/adapters/outbound/aeat/export/test_live_submit_permanently_forbidden.py src/aeat/adapters/outbound/aeat/export/test_engine.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py src/aeat/entrypoints/cli/submission/test_no_submit_command.py -q`
