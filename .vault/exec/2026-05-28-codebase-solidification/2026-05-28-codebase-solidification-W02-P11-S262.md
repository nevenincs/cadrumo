---
step_id: S262
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S262

**Raise sites:** `src/aeat/core/config.py:1249,1252`

**Change:** Replaced 2 `raise ValueError(...)` with `raise CoreValidationError(...)`.

**Architecture decision:** The plan named `ConfigBoundaryError` but `ConfigBoundaryError` lives at `aeat.entrypoints.cli._config._errors` (a higher hexagonal layer). Importing it from `aeat.core.config` would violate the hexagonal boundary (core must not import from entrypoints). `CoreValidationError` is the correct core-layer typed validation error (`CoreValidationError` inherits `CoreError(AeatError)` and `ValueError`), preserving the `ValueError` compatibility contract while enrolling the error.

**Tests:** `test_storage_route_classification.py` updated assertions from `ValueError` to `CoreValidationError`; 9 tests pass.

**Commit:** `d76cbf66e`
