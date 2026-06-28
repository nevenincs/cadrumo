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

# Phase 5 Step 15 Execution

Physically deleted legacy declaración extractor modules:

- Removed all per-model `modelo_*.py` files from the declaration extractor
  package.
- Removed the old Modelo 100 parser package.
- Removed the orphaned generic declaration extractor engine and public export.
- Replaced the remaining successful extraction test suites with fail-closed
  deletion/boundary tests for the registry and Modelo 130 / 303 modules.
- Updated corpus tests so Modelo 840 labels no longer depend on a Python
  extractor class map.
- Updated declaration parser package and extractor docstrings so they no
  longer claim concrete extractors are registered in `_extractors` or routed by
  `get_extractor`.
- Strengthened deletion gates to assert the per-model extractor files and old
  Modelo 100 parser directory are absent.

Rationale:

- Keeping orphaned extractor modules after disabling dispatch would preserve
  Python-owned modelo/casilla/template truth as an importable shadow authority.
- The hard cut requires the old extractor implementations and tests that
  endorse them to be removed, not merely bypassed.

Verification:

- `uv run --no-sync ruff check` on touched declaration, corpus, and deletion
  gate files.
- `uv run --no-sync ty check`
- `uv run --no-sync pytest src\aeat\adapters\inbound\declaracion tests\import_contract\test_registry_deletion_gates.py src\aeat\domain\casillas\test_corpus_coverage.py src\aeat\domain\casillas\test_corpus_rule_alignment.py::test_corpus_casilla_ids_match_extractor_for_extractor_backed_modelos src\aeat\domain\casillas\test_corpus_rule_alignment.py::test_corpus_modelo_840_label_es_matches_extractor_text_labels`
- `rg` confirmed old direct imports, generic extractor references, and
  successful extraction expectations were removed from the declaration test
  surface.

Result: ruff passed, full ty passed, and the focused pytest slice passed with
38 passed.

Residual risk:

- `parse_declaracion` remains as the public entry point, but it reaches the
  fail-closed `get_extractor` boundary until registry-backed extraction lands.
