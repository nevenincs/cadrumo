---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S538'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S538`

DOCUMENT: Classify all `ValueError` raises in `operator_surface/_models.py` as pydantic-validator invariants (developer-surface-only). No code changes — documentation only.

- Modified: `src/aeat/application/operator_surface/_models.py` (module docstring section added)

## Description

All `ValueError` raises in the module exist inside pydantic `@field_validator` and `@model_validator` methods. Pydantic v2 wraps these into `ValidationError` before they surface to callers. They are intentional developer-surface invariants that enforce model construction contracts, not user-facing error paths. A module docstring section titled "S538 invariant-guard classification note" was added explaining this pattern and confirming that using `AeatError` in these sites would bypass pydantic's wrapping and break the `ValidationError` contract.

No grep-post-condition required (documentation-only step; existing `ValueError` raises are correct by design).

## Tests

No new tests required. Existing model validation tests remain the enforcement surface.
