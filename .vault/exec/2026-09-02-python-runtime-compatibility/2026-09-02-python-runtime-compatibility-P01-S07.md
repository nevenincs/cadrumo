---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c6aa0728589caea63e051ca3a805c54d14112b20383f925615f7161ec4613225'
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

