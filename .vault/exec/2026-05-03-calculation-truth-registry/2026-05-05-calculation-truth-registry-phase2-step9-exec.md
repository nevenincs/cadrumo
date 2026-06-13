---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step9-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 9`

Moved declaration verification thresholds and expected computed casillas to the
registry expectation surface.

- Modified: `src/aeat/application/verification/_verify.py`
- Modified: `src/aeat/application/verification/_schema.py`
- Modified: `src/aeat/application/verification/test_verify.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step9-review.md`

## Description

Declaration verification now fails when the active registry snapshot has no
verification expectations. Computed casilla coverage, verification tolerance,
and minimum coverage are read from registry expectations rather than local
constants.

Modelo 130 verification tests now supply the required previous-year binding
value, matching the registry binding declared for the formula graph.

Verification verdicts now persist the registry verification expectation ids that
governed discrepancy and coverage evaluation.

## Tests

`uv run pytest src\aeat\application\verification -q`

`uv run ruff check src\aeat\application\verification`

`uv run ty check src\aeat\application\verification`

`uv run pytest src\aeat\application\filing src\aeat\application\workflow src\aeat\application\verification -q`

`uv run ruff check src\aeat\application\filing src\aeat\application\workflow src\aeat\application\verification`

`uv run ty check src\aeat\application\filing src\aeat\application\workflow src\aeat\application\verification`
