---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# Phase 5 Step 14 Execution

Disabled the legacy declaración extractor registry:

- Replaced the per-model extractor registry package initializer with a
  fail-closed `get_extractor` boundary.
- Removed `_REGISTERED_CLASSES`, `_REGISTRY`, and imports of model-specific
  extractor modules from the public dispatch package.
- Changed `registered_extractors` to fail closed instead of exposing
  Python-registered extractor classes.
- Updated registry-inspection tests to assert the fail-closed boundary.
- Updated corpus coverage tests so they no longer import extractor registry
  constants as corpus authority.
- Added deletion gates proving the registry package does not import
  model-specific extractors or expose legacy registry constants.
- Updated stale docstrings in the parser, schema, errors, and detection modules
  through the required documentation research/author/editor workflow.

Rationale:

- Modelo/template extractor dispatch is legal corpus structure and must be
  backed by validated registry snapshots.
- The codebase must not infer supported declaración templates from imported
  Python classes or class-level `TemplateRevision` literals.

Verification:

- `uv run --no-sync ruff check` on touched declaration files and deletion gates.
- `uv run --no-sync ty check src\aeat\adapters\inbound\declaracion tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\adapters\inbound\declaracion\test_quarterly_extractors.py::TestRegistryKnowsNewExtractors::test_registry_dispatch_requires_registry_snapshot src\aeat\adapters\inbound\declaracion\test_quarterly_extractors.py::TestHeaderOnlyExtractors::test_no_modelo_remains_unconditionally_header_only src\aeat\domain\casillas\test_corpus_coverage.py src\aeat\domain\casillas\test_corpus_rule_alignment.py::test_corpus_casilla_ids_match_extractor_for_extractor_backed_modelos`
- `rg` confirmed removed registry anchors are absent from implementation code.

Result: ruff passed, ty passed, and the focused pytest slice passed with
34 passed.

Residual risk:

- Concrete per-model extractor modules still exist and can be imported directly.
  Public dispatch and inspection no longer reach them.
- A broad ruff scan of the full declaration package still reports an existing
  unrelated ambiguous fullwidth-parenthesis lint in `modelo_130_v2025.py`.
