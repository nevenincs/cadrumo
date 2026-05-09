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

# `calculation-truth-registry` `Renta` `construct dependency closure`

Hardened the central registry validator so construct-owned dependency
classifications are checked by the same closure path as casillas, formulas,
bindings, relations, applications, and source-backed members.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The construct closure now validates `dependency_classifications` entries. A
Modelo 100 construct cannot silently reference a dependency classification that
is absent from the selected revision, and the existing construct legal/source
coverage checks now apply to dependency classification members as well.

The behaviour test mutates the loaded Modelo 100 registry object and verifies a
hard validation failure when a Renta construct points at an undeclared
dependency classification.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_validator_rejects_construct_dependency_classification_outside_revision -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
