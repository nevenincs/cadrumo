---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S22'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P07.S22 Execution

Aligned residual verification with the active hexagonal pytest marker taxonomy.

Change:
- Updated `src/aeat/tests/_marker_hook.py` from the retired `domain_*` marker requirement to the active `hex_*` marker requirement.
- Updated the repo-root `conftest.py` comment to describe the active marker hook.

Verification:
- `uv run --no-sync pytest src/aeat/tests/test_marker_integrity.py -q` passed with 2101 marker-integrity checks.
- CLI behavior tests now collect under the appropriate `integration` lane instead of failing on the retired marker rule.
