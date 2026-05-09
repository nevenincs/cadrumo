---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step1-exec]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `calculation-truth-registry` `Wave 4` `Modelo 123 verification boundary`

Added Modelo 123 export and declaration verification coverage through public
application APIs.

- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/application/verification/test_verify.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`verify_export` now has a Modelo 123 behaviour test that exports an approved
current-revision draft through the committed registry layout and re-reads the
generated payload against the approved draft.

`verify_declaracion` now has Modelo 123 behaviour tests for both the current
revision and the historical 2019-through-2023 revision. Each test supplies a
parsed declaration observation and verifies it against the selected registry
calculation expectation. The tests do not define local schemas, formulas, or
model-specific verification tables.

The plan now records the Modelo 123 export-verification and
declaration-verification boundaries under the Wave 4 export/filing linkage row.
The broader export/filing linkage row remains open because review, approval,
reconciliation, and workflow linkage still need complete current-surface
coverage.

## Tests

- `uv run ruff check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run ty check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run pytest src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py -q`
