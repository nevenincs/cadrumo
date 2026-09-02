---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:fbb2f8c7d5551d94006f2915417bbedc70bb73fee78ce0b3f43a27d3d7c01032'
step_id: 'S06'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Replace the stale Python ceiling assertion with the open-floor policy

## Scope

- `dev/audit/security.py`

## Changes

- `M` `dev/audit/security.py`
- `verify:` `uv run --no-sync ruff check dev/audit/security.py; uv run --no-sync python -c "from pathlib import Path; text=Path('dev/audit/security.py').read_text(encoding='utf-8'); assert 'requires Python' in text and 'no upper bound' in text; assert '>=3.13,<3.14' not in text; assert '>=3.13,<3.15' not in text"` -> `pass`
