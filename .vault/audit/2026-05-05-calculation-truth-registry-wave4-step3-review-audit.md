---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step3-exec]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `calculation-truth-registry-wave4-step3` Code Review

No blocking findings.

Reviewed scope:

- `src/aeat/application/filing/test_export.py`, limited to the new Modelo 123
  export-verification assertion.
- `src/aeat/application/verification/test_verify.py`, limited to the new Modelo
  123 current and historical declaration-verification assertions.
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`, limited
  to the Modelo 123 verification tracking rows.
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-05-calculation-truth-registry-wave4-step3.md`.

Checks performed:

- The export-verification test writes an approved current-revision Modelo 123
  draft through the committed registry layout and verifies the generated
  payload through the public verification API.
- The declaration-verification tests exercise registry revision selection for
  both the current and historical Modelo 123 revisions.
- The tests assert public verification outcomes and registry snapshot ids; they
  do not create local schemas, local formulas, or isolated verification tables.
- The broader Modelo 123 linkage row remains open because additional public
  filing surfaces still need coverage.

Verification reviewed:

- `uv run ruff check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run ty check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run pytest src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py -q`
