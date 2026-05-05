---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-construct-classification-reciprocity]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code. -->

# `calculation-truth-registry` Code Review

No blocking issues were found in the construct classification reciprocity slice.

The validator change in `_validate.py` requires dependency classifications to be
listed by every construct they target. The focused mutation test in
`test_modelo_100_registry.py` exercises validator behavior by removing a real
construct membership and asserting validation fails. The Modelo 180, Modelo 190,
and Modelo 193 registry definitions now satisfy the reciprocal ownership rule
for their annual-summary constructs.

Verification recorded by review:

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- registry-wide validation for all loaded modelos
- `git diff --check`
