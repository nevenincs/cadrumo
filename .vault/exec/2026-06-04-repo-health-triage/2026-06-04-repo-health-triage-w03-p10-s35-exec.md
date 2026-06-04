---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
step_id: 'S35'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P10.S35 extract identity multi-declaration analyzer

Scope: `W03.P10` diagnostics complexity reduction.

## Description

- Extract the clause-9 same-name constant scan into `_SameNameConstantMultiDeclarationAnalyzer`.
- Add `_ConstantDeclaration` and `_iter_literal_module_constants` to separate literal extraction, registry collection, duplicate grouping, and finding rendering.
- Keep the public `find_same_name_constant_multi_declarations` API unchanged for the placement tests.

## Outcome

The identity-placement multi-declaration detector now has a named analyzer boundary and a smaller public function while preserving existing diagnostics behavior.

## Notes

Verification completed:

- `uv run --no-sync ruff check src/aeat/diagnostics/_identity_placement.py src/aeat/diagnostics/test_identity_primitive_placement.py`
- `uv run --no-sync ty check src/aeat/diagnostics/_identity_placement.py --output-format concise`
- `uv run --no-sync pytest src/aeat/diagnostics/test_identity_primitive_placement.py::test_no_same_name_constant_multi_declarations src/aeat/diagnostics/test_identity_primitive_placement.py::test_same_name_constant_detector_flags_synthetic_violation -q`
- `uv run --no-sync pytest src/aeat/diagnostics/test_identity_primitive_placement.py -q`
