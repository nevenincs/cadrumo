---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step2-exec]]'
---



# `calculation-truth-registry-wave4-step2` Code Review

No blocking findings.

Reviewed scope:

- `src/aeat/domain/deadlines/test_engine.py`, limited to Modelo 123 deadline
  applicability assertions.
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`, limited
  to the Modelo 123 current-deadline applicability tracking row.
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-05-calculation-truth-registry-wave4-step2.md`.

Checks performed:

- The test exercises `DeadlineEngine.compute` and `applies_to` with the
  committed registry data.
- The applicability trigger is the existing profile field
  `pays_capital_income_with_retencion`; no model-specific branching or local
  deadline table was added to Python.
- The test asserts behaviour at the public schedule boundary rather than
  copying registry row values into an isolated fixture.
- Registry verification confirms the committed 123 snapshot remains valid with
  deadline surfaces present.

Verification reviewed:

- `uv run ruff check src\aeat\domain\deadlines\test_engine.py`
- `uv run ty check src\aeat\domain\deadlines\test_engine.py`
- `uv run pytest src\aeat\domain\deadlines\test_engine.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
