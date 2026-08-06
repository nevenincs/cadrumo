---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-07-17'
body_hash: 'sha256:ccc03ee4a07c6caa03c0475d719906c753d477dca6260fe328c69b22b032c035'
step_id: 'S156'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P06.S156`

Add `test_taxation_comparison_module_imports_cleanly` to the existing test module, asserting that `aeat.application.modelo._taxation_comparison` imports without error and exposes its three public symbols after the S155 TYPE_CHECKING cleanup.

- Modified: `src/aeat/application/modelo/test_taxation_comparison.py`

## Description

The test uses `importlib.import_module` — a real production import, no mocks — and asserts `hasattr` on `compare_taxation_modes`, `TaxationComparisonResult`, and `TaxationComparisonError`. This verifies the module's top-level import chain is intact after the dead-block removal.

## Tests

`test_taxation_comparison_module_imports_cleanly` passed in the targeted run (23/23 passed, 47 s). Commit SHA: 74f07401b.
