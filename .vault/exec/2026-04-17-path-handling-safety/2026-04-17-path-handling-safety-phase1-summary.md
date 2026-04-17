---
tags:
  - "#exec"
  - "#path-handling-safety"
date: "2026-04-17"
related:
  - "[[2026-04-17-path-handling-safety-phase1-plan]]"
---

# `path-handling-safety` `phase1` summary

Phase 1 closed the critical path-handling findings from the rolling audit.

- Modified: `src/aeat/config.py`
- Modified: `src/aeat/sync/_repository.py`
- Modified: `src/aeat/submission/_engine.py`
- Modified: `src/aeat/filing/_complementaria.py`
- Modified: `src/aeat/workflow/_persistence.py`
- Modified: `src/aeat/manuals/_schema.py`
- Modified: `src/aeat/manuals/_loader.py`
- Modified: `src/aeat/manuals/_fetch.py`
- Modified: `src/aeat/storage/engine.py`
- Modified: `tests/test_config.py`
- Modified: `src/aeat/sync/test_repository.py`
- Modified: `src/aeat/submission/test_engine.py`
- Modified: `src/aeat/filing/test_complementaria.py`
- Modified: `src/aeat/workflow/test_persistence.py`
- Modified: `src/aeat/manuals/test_loader.py`
- Modified: `src/aeat/manuals/test_fetch.py`
- Modified: `src/aeat/storage/_test_engine.py`
- Created: `src/aeat/_paths.py`
- Created: `2026-04-17-path-handling-safety-review.md`

## Description

The remediation consolidated path safety around a single helper layer, removed direct `<root>/<id>.json` joins from file-backed persistence surfaces, enforced contained manuals-relative paths both in schema validation and at runtime, and anchored repo-relative env paths plus SQLite URLs to `PROJECT_ROOT`.

## Tests

- `uv run pytest tests/test_config.py src/aeat/sync/test_repository.py src/aeat/workflow/test_persistence.py src/aeat/submission/test_engine.py src/aeat/filing/test_complementaria.py src/aeat/manuals/test_loader.py src/aeat/manuals/test_fetch.py src/aeat/storage/_test_engine.py`
- `uv run ruff check src/aeat/_paths.py src/aeat/config.py src/aeat/sync/_repository.py src/aeat/sync/test_repository.py src/aeat/submission/_engine.py src/aeat/submission/test_engine.py src/aeat/filing/_complementaria.py src/aeat/filing/test_complementaria.py src/aeat/workflow/_persistence.py src/aeat/workflow/test_persistence.py src/aeat/manuals/_schema.py src/aeat/manuals/_loader.py src/aeat/manuals/_fetch.py src/aeat/manuals/test_loader.py src/aeat/manuals/test_fetch.py src/aeat/storage/engine.py src/aeat/storage/_test_engine.py tests/test_config.py`
