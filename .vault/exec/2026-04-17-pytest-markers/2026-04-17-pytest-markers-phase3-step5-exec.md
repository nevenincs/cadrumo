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

# pytest-markers phase-3 step-5

## migrate-domain-mediation-test-modules

Applied module-level `pytestmark` per inventory across the 14 modules under `workflow/`, `llm/`, `i18n/`, `testing/`. Two modules received `live_read`: `workflow/test_live.py`, `llm/test_live_anthropic.py`.

## verification

- `uv run pytest src/aeat/workflow src/aeat/llm src/aeat/i18n src/aeat/testing -m unit` -> green.
