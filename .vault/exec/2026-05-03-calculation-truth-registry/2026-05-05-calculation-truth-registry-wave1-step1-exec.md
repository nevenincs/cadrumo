---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `modelo-130` `legal-live-verification`

Added a real-behaviour Modelo 130 verification that parses the committed
redacted AEAT submitted-file fixture through the registry export layout,
asserts the fixed Modelo 130 computed-casilla surface, resolves the required
prior-filing binding through the registry filed-data layer, feeds the observed
manual casillas into the registry calculation engine, and compares the
computed casillas back to the filed values.

- Modified: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Modified: `src/aeat/domain/deadlines/_models.py`
- Modified: `src/aeat/application/workflow/_errors.py`
- Modified: `src/aeat/adapters/persistence/storage/_path_safety.py`
- Modified: test fixture modules under `tests/fixtures/pdf_corpus/`
- Modified: `tests/conftest.py`
- Modified: `tests/import_contract/adapters/outbound/aeat/verify/test_verify_live.py`

## Description

The Modelo 130 verification now exercises live-filed data at the behavioural
boundary: a sanitized submitted-file artefact is parsed, context-bound to the
declaration row, converted into observed casilla values, checked against the
expected Modelo 130 computed-casilla set, paired with a registry-resolved
previous-filing observation, and checked against the registry formulas. This
closes the gap between "the parser saw fields" and "the centralized
calculation authority produces the same filed computed casillas".

The documentation strings and comments touched in this step were also cleaned
of development-process labels and stale module references. No runtime logic,
schema aliases, compatibility shim, or model-specific alternate authority was
added.

## Tests

- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestSubmittedFileObservation::test_modelo_130_redacted_submitted_file_matches_registry_calculation -q`
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestSubmittedFileObservation src\aeat\domain\deadlines\test_engine.py tests\fixtures\pdf_corpus\l3_synthetic\_generators\test_generator_shared.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\domain\calculations\registry\test_formula_runtime.py src\aeat\domain\calculations\registry\test_workbook_parity.py src\aeat\application\filing\test_calculate.py src\aeat\application\filing\test_export.py src\aeat\application\filing\test_import.py src\aeat\application\filing\reconciliation\test_reconcile.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\outbound\aeat\sede\test_observation_store.py src\aeat\domain\deadlines\test_engine.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestReadOperationGuard -q`
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestSubmittedFileObservation src\aeat\domain\calculations\registry\test_formula_runtime.py src\aeat\adapters\outbound\aeat\sede\test_observation_store.py -q`
- `uv run ruff check ...`
- `uv run ty check ...`
- `git diff --check -- ...`
- `rg -n "EPIC|Issue #|issue #|back-compat|hard_cut|runtime_authority|transient dev|wave [0-9]|Wave [0-9]|MVP" src\aeat tests -g "*.py" -g "*.json" -g "*.md"`
