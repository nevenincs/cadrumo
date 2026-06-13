---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase0b` `step33`

Closed the remaining authority-tier framework gaps for model-law coverage and
live AEAT guard classification.

- Created: `src/aeat/domain/calculations/registry/_coverage.py`
- Modified: `registry/aeat/modelos/130.toml`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_remote_state_guard.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Added a model-law coverage ledger API that reports the four evidence gates
independently: legal authority, official source guidance, executable parity
evidence, and layout authority. Tests now exercise behavior by changing evidence
tiers and verifying that coverage moves between gates instead of restating
committed identifiers.

Live cross-reference definitions now carry an evidence tier. Open simulator and
integration-test surfaces require executable parity evidence. Static official
documentation cannot be labelled as executable parity evidence. The remote-state
guard policy enforces the same distinction independently of registry loading.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/domain/calculations/registry/test_workbook_parity.py -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry registry/aeat/legal/irpf.toml registry/aeat/modelos/130.toml`
- `uv run ty check src/aeat/domain/calculations/registry`
- Corpus workbook verification: 72 artefacts, 47 record-design XLSX, 25 binary XLS, zero failed scans, all classified as layout authority.
