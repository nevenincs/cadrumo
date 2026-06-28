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

# pytest-markers phase-1 step-1

## rewrite-pyproject-marker-table-and-addopts

Rewrote `[tool.pytest.ini_options]` in `pyproject.toml`:

- `addopts` changed from `"-v --tb=short -m 'not live'"` to `"-v --tb=short -m 'unit'"`.
- Removed the stale `live` marker entry.
- Registered the nine-entry ADR taxonomy: `unit`, `live_read`, `live_write`, `domain_aeat_remote`, `domain_submission`, `domain_financial_input`, `domain_local_state`, `domain_mediation`, `domain_infra`. Each line uses the description copy mandated by the plan.

Files touched: `pyproject.toml`.

## verification

- `uv run pytest --collect-only -q 2>&1 | grep -c PytestUnknownMarkWarning` -> 0 after phase 3 completed.
- `grep -n "live_write\|domain_" pyproject.toml` confirms all nine markers present.
