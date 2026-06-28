---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S15'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P05.S15 Execution

Verified the live residual extraction.

Passed:
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestBorrador100Subgroup -q`
- `uv run --no-sync ruff check ... _app_live.py _app_live_borrador_cli.py ...`
- `uv run --no-sync python -m compileall -q ... _app_live.py _app_live_borrador_cli.py ...`

Behavior:
- `borrador 100 list`, `latest`, `view`, unknown id refusal, invalid state refusal, and seeded lifecycle behavior all pass through the extracted Typer subgroup.
