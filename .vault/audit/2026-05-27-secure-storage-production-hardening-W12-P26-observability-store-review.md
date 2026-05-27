---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-observability-store-persistence-closeout-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-storage-production-hardening` Code Review

<!-- Persistent log of audit findings appended below. -->

OBS-001 | HIGH | Successful `run_context` exits could still hide trace persistence failure

The first implementation wrapped direct store read/write filesystem failures in `RunTracePersistenceError`, but the primary `run_context` exit path still caught broad `Exception` around `save_trace(trace)` and only logged a warning. That allowed a clean command body to return success even when final `trace.json` persistence failed.

Resolution: `run_context` now re-raises the persistence failure after sink cleanup when the command body completed with `RunOutcome.OK`, while still preserving an already-propagating body failure. Regression coverage was added for both clean-exit fail-closed behavior and body-error precedence.

Validation:

- `uv run ruff check src/aeat/core/observability/__init__.py src/aeat/core/observability/_context.py src/aeat/core/observability/_errors.py src/aeat/core/observability/_models.py src/aeat/core/observability/_recorder.py src/aeat/core/observability/_store.py src/aeat/core/observability/test_context_propagation.py src/aeat/core/observability/test_sink.py src/aeat/core/errors/registry/_core.py src/aeat/core/errors/test_registry.py`
- `uv run pytest src/aeat/core/observability/test_context_propagation.py src/aeat/core/observability/test_sink.py src/aeat/core/observability/test_models.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q`
