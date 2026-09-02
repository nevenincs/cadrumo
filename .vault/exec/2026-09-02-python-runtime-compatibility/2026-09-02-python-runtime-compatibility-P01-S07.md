---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:7a2e8aa265b9ddaf091353af62b295ee7a6095ab1e25e21a542311ecb7e66341'
step_id: 'S07'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Update security-audit expectations for the open-ended floor

## Scope

- `dev/audit/tests/test_security.py`

## Changes

- `M` `dev/audit/tests/test_security.py`
- `verify:` `uv run --no-sync pytest -q dev/audit/tests/test_security.py; uv run --no-sync ruff check dev/audit/tests/test_security.py dev/audit/security.py` -> `pass`
