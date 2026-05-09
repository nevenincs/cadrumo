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

# `calculation-truth-registry` `period-aware relation resolution`

Hardened cross-model relation resolution so filed-declaration observations are
selected by the active target filing period before relation values are required.

- Modified: `src/aeat/domain/calculations/registry/_relations.py`
- Modified: `src/aeat/domain/calculations/registry/test_relation_closure.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`relation_source_requirements` already selected relation requirements by target
period, but observation-based resolution delegated into the generic relation
resolver without the active period. That forced callers to provide annual
relation observations even when the requested period had no active relations.

The resolver now accepts an optional target period and only requires relation
values active for that period. Observation-based resolution passes the requested
period through to the resolver. The real Modelo 180 annual-summary relation
surface now proves that a quarterly period with no active annual-summary
relations resolves to an empty relation-value set instead of a missing-relation
failure.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_relation_closure.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_relation_closure.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_relation_closure.py`
