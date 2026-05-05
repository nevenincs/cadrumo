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

# `calculation-truth-registry` `relation treatment requirements`

Extended relation source requirements so callers receive the dependency
treatment declared by the central registry classification.

- Modified: `src/aeat/domain/calculations/registry/_relations.py`
- Modified: `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`relation_source_requirements` now derives each source requirement from the
relation and its registry dependency classification. The returned requirement
includes `dependency_treatment`, and the function fails hard if a relation
source has no classification. This lets Renta callers distinguish
annual-settlement inputs from factual evidence while still using the same
observation resolver.

The generalized contract test now proves every derived requirement reports the
treatment declared by the registry classification.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_contract.py src/aeat/domain/calculations/registry/test_relation_closure.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- `uv run ty check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
