---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-5 step-1

## update-claude-md-testing-paragraph

Rewrote the testing paragraph in `CLAUDE.md` to describe the new marker taxonomy:

- Axis A: exactly one of `unit`, `live_read`, `live_write`.
- Axis B: at least one of six `domain_*` markers enumerated by name.
- Module-level mandate via `pytestmark = [...]`; per-function access/domain markers forbidden.
- `live_read` opt-in via `AEAT_LIVE_TESTS_ENABLED=1`; Google Workspace additionally requires `AEAT_LIVE_TESTS_GOOGLE=1`.
- `live_write` collection-banned by default; zero `live_write` tests exist today; see `tests/README.md` and charter #116.
- Mocks/stubs permitted in unit tests; forbidden in all live tests.

Files touched: `CLAUDE.md`.

## verification

- `grep -n "live_read\|live_write\|domain_" CLAUDE.md` shows the new taxonomy.
- `uv run pytest tests/test_docs.py -m unit` -> green.
