---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step6-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 6`

Hardened complementaria construction against missing official filing linkage and
non-registry original drafts.

- Modified: `src/aeat/application/filing/_complementaria.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step6-review.md`

## Description

Complementaria construction now rejects submitted-filing records without an
official justificante CSV before reading or persisting amendment data.

The persisted original draft must also match the active registry schema
provided to the complementaria use case. A draft whose schema version does not
match the registry provider cannot be used as amendment input.

## Tests

`uv run pytest src\aeat\application\filing\test_complementaria.py -q`

`uv run ruff check src\aeat\application\filing\_complementaria.py src\aeat\application\filing\test_complementaria.py`

`uv run ty check src\aeat\application\filing\_complementaria.py src\aeat\application\filing\test_complementaria.py`
