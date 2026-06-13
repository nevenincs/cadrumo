---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P04` summary

Completed the aggregation source-kind taxonomy phase.

- Modified: `src/aeat/core/aggregation.py`
- Modified: `src/aeat/application/aggregation/_counterpart.py`
- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_counterpart_bindings.py`

## Description

Counterpart source-kind narrowing is now centralized in `aeat.core.aggregation`.
Application and registry surfaces consume the same enum-backed subset, and the
retired bare `invoice` alias remains a rejected compatibility value rather than a
valid counterpart source.

## Verification

- `uv run --no-sync ruff check` on W02 touched Python files: exit 0.
- Focused `ty check` on W02 files: exit 0; all checks passed.
- Focused Pyright on W02 files: exit 0; 0 errors and 23 warnings.
- Focused aggregation and registry pytest group: exit 0; 79 passed.
