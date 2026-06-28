---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step4-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 4`

Hardened filing approval so approval cannot be stamped onto a draft that no
longer matches the active registry schema and formula trace surface.

- Modified: `src/aeat/application/filing/_review.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step4-review.md`

## Description

Approval now recomputes registry-backed filing validation before writing
approval metadata. Schema-version mismatch or formula-trace mismatch raises a
filing draft error instead of relying on previously persisted findings.

Review refresh still uses approval-basis fingerprints to derive approval
staleness for already approved drafts.

The export verification test now narrows registry export field length before
mutating the payload, so the full filing type check can verify the test surface.

## Tests

`uv run pytest src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_calculate.py -q`

`uv run ruff check src\aeat\application\filing\_review.py src\aeat\application\filing\test_filing.py`

`uv run ty check src\aeat\application\filing\_review.py src\aeat\application\filing\test_filing.py`

`uv run pytest src\aeat\application\filing\test_export.py -q`

`uv run ruff check src\aeat\application\filing`

`uv run ty check src\aeat\application\filing`
