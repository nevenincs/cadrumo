---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step5-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 5`

Audited the declaration calculation summary surface and removed its test-owned
draft shape.

- Modified: `src/aeat/application/filing/test_calculate.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step5-review.md`

## Description

The calculation summary module remains a rendering/reporting boundary: it
counts findings and derives the next operator action from an already built
filing draft. It does not perform schema, formula, or legal validation.

The calculation summary tests now build drafts through registry-backed public
helpers instead of constructing local filing values and schema versions. The
enum literal mirror test was removed.

## Tests

`uv run pytest src\aeat\application\filing\test_calculate.py -q`

`uv run ruff check src\aeat\application\filing\test_calculate.py`

`uv run ty check src\aeat\application\filing\test_calculate.py`
