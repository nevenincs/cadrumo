---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-informative-workflow-links-exec]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline code: `src/module.py`. -->

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
