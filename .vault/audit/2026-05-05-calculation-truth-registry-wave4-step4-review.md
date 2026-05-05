---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step4]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `calculation-truth-registry-wave4-step4` Code Review

No blocking findings.

Reviewed scope:

- `src/aeat/application/filing/test_filing.py`, limited to the new Modelo 123
  build and approval assertions.
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`, limited
  to the Modelo 123 application filing tracking row.
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-05-calculation-truth-registry-wave4-step4.md`.

Checks performed:

- The build test uses the committed runtime registry provider and public filing
  API to compute current-revision Modelo 123 casillas.
- The approval test verifies the public approval path preserves a
  schema/formula fingerprint from the registry snapshot.
- The tests assert formula traces and computed values from registry execution;
  they do not define local schemas, copied formula graphs, or fallback
  providers.
- The broader Modelo 123 linkage row remains open for review, reconciliation,
  workflow, and remaining public surfaces.

Verification reviewed:

- `uv run ruff check src\aeat\application\filing\test_filing.py`
- `uv run ty check src\aeat\application\filing\test_filing.py`
- `uv run pytest src\aeat\application\filing\test_filing.py -q`
