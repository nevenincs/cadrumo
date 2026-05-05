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

# `calculation-truth-registry` `Wave 4` `Modelo 123 reconciliation boundary`

Added Modelo 123 reconciliation coverage through the registry-gated
justificante comparison surface.

- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The reconciliation suite now includes a Modelo 123 draft built through the
registry filing helper and a justificante record whose payable total matches
the registry-declared total casilla for the active revision.

The test exercises the public `reconcile` boundary. It proves that the payable
total is projected from the registry verification expectation instead of a
Python-side modelo branch or local reconciliation table.

## Tests

- `uv run ruff check src\aeat\application\filing\reconciliation\test_reconcile.py`
- `uv run ty check src\aeat\application\filing\reconciliation\test_reconcile.py`
- `uv run pytest src\aeat\application\filing\reconciliation\test_reconcile.py -q`
