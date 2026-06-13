---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step8-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 8`

Removed ambiguous workflow draft input loading.

- Modified: `src/aeat/application/workflow/_adapters.py`
- Modified: `src/aeat/application/workflow/_engine.py`
- Modified: `src/aeat/application/workflow/_protocols.py`
- Modified: `src/aeat/application/workflow/__init__.py`
- Added: `src/aeat/application/workflow/test_adapters.py`
- Modified: `src/aeat/application/workflow/test_engine.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step8-review.md`

## Description

The default workflow JSON input provider now requires explicit
``modelo -> period -> inputs`` shape. Root-level casilla payloads are rejected
instead of being treated as draft inputs.

The filing draft builder remains responsible for registry validation of the
resulting inputs.

The workflow engine now writes plain string summaries into `WorkflowStep`, which
matches the strict workflow schema and removes the previous casted dictionary
payload.

The workflow protocol layer now exposes a registry-backed draft protocol with a
`schema_version` field. The engine aborts during draft construction when the
built draft does not match the resolved obligation's modelo, period, taxpayer,
or registry schema namespace.

## Tests

`uv run pytest src\aeat\application\workflow\test_adapters.py -q`

`uv run ruff check src\aeat\application\workflow\_adapters.py src\aeat\application\workflow\test_adapters.py`

`uv run ty check src\aeat\application\workflow\_adapters.py src\aeat\application\workflow\test_adapters.py`

`uv run pytest src\aeat\application\workflow -q`

`uv run ruff check src\aeat\application\workflow`

`uv run ty check src\aeat\application\workflow`
