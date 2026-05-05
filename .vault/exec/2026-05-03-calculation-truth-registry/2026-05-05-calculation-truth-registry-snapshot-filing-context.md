---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `calculation-truth-registry` `snapshot filing context`

Added selected filing context to registry snapshots and used that context when
validating relation values supplied to the formula runtime.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_snapshot.py`
- Modified: `src/aeat/domain/calculations/registry/_formula_runtime.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`build_snapshot` now persists the selected filing year and period on the
immutable `RegistrySnapshot`. This makes the snapshot carry its legal filing
context explicitly instead of relying on downstream callers to remember the
period used during revision selection.

The formula runtime now validates supplied relation values against the
relations active for `snapshot.period`. This aligns runtime validation with the
period-aware relation requirement and observation-resolution layer.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_snapshot.py src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_snapshot.py src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
