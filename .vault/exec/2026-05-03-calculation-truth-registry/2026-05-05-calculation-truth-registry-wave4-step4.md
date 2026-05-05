---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step1]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `calculation-truth-registry` `Wave 4` `Modelo 123 filing boundary`

Added Modelo 123 build and approval coverage through the public filing API.

- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`build_draft` now has a Modelo 123 behaviour test that exercises the committed
runtime registry provider for the current revision and checks the computed
capital-income aggregation casillas 03, 06, 09, 12, and 14 plus their formula
traces.

`approve_draft` now has a Modelo 123 behaviour test that approves a registry
draft and verifies that the approval surface carries a schema/formula
fingerprint from the active registry snapshot.

The tests use public filing APIs and committed registry definitions. They do
not define local casilla schemas, copied formulas, or model-specific filing
providers.

## Tests

- `uv run ruff check src\aeat\application\filing\test_filing.py`
- `uv run ty check src\aeat\application\filing\test_filing.py`
- `uv run pytest src\aeat\application\filing\test_filing.py -q`
