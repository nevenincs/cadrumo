---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d2735fe36d90c944dee69c26b22006fe60633d8318819f18458c452fbc51136e'
step_id: 'S310'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the session-vocabulary custody regex census, its two owning-module rosters, qualifier vocabulary, symbol exemptions, and rename history; retain receipt and authority-session custody behavior.

## Scope

- `session vocabulary custody test`
- `focused custody tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_session_vocabulary_custody_split.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S310.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py src/cadrumo/application/user_profile/tests/test_login_session_port.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Receipt and authority-session custody remain proven by 32 focused encryption, resume, revocation, and application-boundary tests. The deleted gate maintained module, qualifier, and symbol rosters rather than exercising custody; the exact production detector remains red on the wider campaign findings.
