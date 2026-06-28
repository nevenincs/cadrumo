---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step1-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 1`

Removed test-local filing schema authority from the primary filing boundary
test module.

- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step1-review.md`

## Description

`test_filing.py` no longer defines private casilla schema dataclasses or a
private schema provider. The tests now build or validate drafts with
`build_runtime_schema_provider`, so formula-trace validation, schema-version
validation, review refresh, approval, and deadline checks all run against the
committed registry-backed runtime projection.

The plan now records this as a completed substep under the filing-test rewrite
row while leaving the broader filing test surface open.

## Tests

`uv run pytest src\aeat\application\filing\test_filing.py -q`

`uv run ruff check src\aeat\application\filing\test_filing.py`

`uv run ty check src\aeat\application\filing\test_filing.py`
