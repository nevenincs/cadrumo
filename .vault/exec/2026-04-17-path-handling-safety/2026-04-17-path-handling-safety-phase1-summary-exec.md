---
tags:
  - "#exec"
  - "#path-handling-safety"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-path-handling-safety-phase1-plan]]"
---

# `path-handling-safety` `phase1` summary

Phase 1 closed the critical path-handling findings from the rolling audit.

- Modified: `src/aeat/config.py`
- Modified: `src/aeat/application/sync/_repository.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_engine.py`
- Modified: `src/aeat/application/filing/_complementaria.py`
- Modified: `src/aeat/application/workflow/_persistence.py`
- Modified: `src/aeat/domain/manuals/_schema.py`
- Modified: `src/aeat/domain/manuals/_loader.py`
- Modified: `src/aeat/domain/manuals/_fetch.py`
- Modified: `src/aeat/adapters/persistence/storage/engine.py`
- Modified: `tests/test_config.py`
- Modified: `src/aeat/application/sync/test_repository.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/test_engine.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `src/aeat/application/workflow/test_persistence.py`
- Modified: `src/aeat/domain/manuals/test_loader.py`
- Modified: `src/aeat/domain/manuals/test_fetch.py`
- Modified: `src/aeat/adapters/persistence/storage/_test_engine.py`
- Created: `src/aeat/_paths.py`
- Created: `2026-04-17-path-handling-safety-review.md`

## Description

The remediation consolidated path safety around a single helper layer, removed direct `<root>/<id>.json` joins from file-backed persistence surfaces, enforced contained manuals-relative paths both in schema validation and at runtime, and anchored repo-relative env paths plus SQLite URLs to `PROJECT_ROOT`.

## Tests

- `uv run pytest tests/test_config.py src/aeat/application/sync/test_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/adapters/outbound/aeat/export/test_engine.py src/aeat/application/filing/test_complementaria.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_fetch.py src/aeat/adapters/persistence/storage/_test_engine.py`
- `uv run ruff check src/aeat/_paths.py src/aeat/config.py src/aeat/application/sync/_repository.py src/aeat/application/sync/test_repository.py src/aeat/adapters/outbound/aeat/export/_engine.py src/aeat/adapters/outbound/aeat/export/test_engine.py src/aeat/application/filing/_complementaria.py src/aeat/application/filing/test_complementaria.py src/aeat/application/workflow/_persistence.py src/aeat/application/workflow/test_persistence.py src/aeat/domain/manuals/_schema.py src/aeat/domain/manuals/_loader.py src/aeat/domain/manuals/_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_fetch.py src/aeat/adapters/persistence/storage/engine.py src/aeat/adapters/persistence/storage/_test_engine.py tests/test_config.py`
