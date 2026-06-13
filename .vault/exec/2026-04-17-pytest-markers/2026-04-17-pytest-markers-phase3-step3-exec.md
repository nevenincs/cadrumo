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

# pytest-markers phase-3 step-3

## migrate-domain-financial-input-test-modules

Applied `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]` to 22 modules across `src/aeat/domain/financial/**` and `src/aeat/entrypoints/cli/financial/`. All tests are `unit`-access.

## verification

- `uv run pytest src/aeat/financial src/aeat/entrypoints/cli/financial -m unit` -> green.
- Integrity test passes for all 22 modules.
