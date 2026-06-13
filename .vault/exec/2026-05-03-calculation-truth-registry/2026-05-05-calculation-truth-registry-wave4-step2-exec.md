---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step1-exec]]'
---



# `calculation-truth-registry` `Wave 4` `Modelo 123 deadline boundary`

Verified current Modelo 123 deadline applicability through the registry-backed
deadline engine.

- Modified: `src/aeat/domain/deadlines/test_engine.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The current Modelo 123 registry definition now has behaviour coverage for the
capital-income withholding profile condition. The deadline engine test proves
that `pays_capital_income_with_retencion` activates the four 2026 quarterly
Modelo 123 obligations and that `applies_to` is false until that profile field
is true.

This closes the previously identified current-deadline applicability gap for
the active Modelo 123 revision without adding Python-side modelo branching.
The test exercises the public deadline engine and the committed registry data.

## Tests

- `uv run ruff check src\aeat\domain\deadlines\test_engine.py`
- `uv run ty check src\aeat\domain\deadlines\test_engine.py`
- `uv run pytest src\aeat\domain\deadlines\test_engine.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
