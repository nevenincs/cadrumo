---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:4f5c96e0243b9c30b0ebd3d283986956f39535d69d845babcbb4e21014096e0d'
step_id: 'S230'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unused LlmReviewRequest envelope, its export and self-only constructor tests, and documentation claiming it is part of the live typed spine; retain the directly consumed invocation-origin and decision enums and the execute_reviewed_decision workflow that every CLI caller actually uses.

## Scope

- `Ledger LLM review workflow and type tests`
- `accepted LLM classification workflow decision`
- `live CLI review callers`
- `exact symbol signal`
- `focused workflow gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/application/ledger/llm_review_workflow.py`
- `M` `src/cadrumo/application/ledger/tests/test_llm_review_workflow_types.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/ledger/llm_review_workflow.py src/cadrumo/application/ledger/tests/test_llm_review_workflow_types.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s230 src/cadrumo/application/ledger/tests/test_llm_review_workflow_types.py src/cadrumo/application/ledger/tests/test_llm_review_workflow.py src/cadrumo/application/ledger/tests/test_llm_reject.py src/cadrumo/application/ledger/tests/test_reviewed_invoice_draft_terminal.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
