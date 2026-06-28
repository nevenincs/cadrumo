---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-informative-workflow-links-exec]]'
---



# `calculation-truth-registry` Code Review

REVIEW-001 | INFO | No findings

The new Modelo 232 and Modelo 720 application links are declarative registry
data only. They do not add formulas, old authority calls, compatibility shims,
legacy aliases, generated-rule inputs, or transient development-state checks.

The behavior tests exercise current registry constructs and application-link
snapshot requirements. They do not compare against a previous implementation or
encode migration state.

## Verification

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_232_registry.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py -q`
  passed.
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_232_registry.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py`
  passed.
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_232_registry.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py`
  passed.
