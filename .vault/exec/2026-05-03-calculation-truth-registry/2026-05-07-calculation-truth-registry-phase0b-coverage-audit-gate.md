---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-07'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-07-calculation-truth-registry-coverage-audit-gate-review]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `calculation-truth-registry` `Phase 0B` `Coverage Audit Gate`

Added a whole-tree coverage audit gate so registry state checks and rollout
tracking move with the implementation.

- Modified: `src/aeat/domain/calculations/registry/_coverage.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_catalogue_verification.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`audit_registry_model_law_coverage` validates the committed registry once, builds
a representative coverage ledger for every modelo revision, and reports whether
mandatory evidence gates are satisfied. Legal authority, official source
guidance, and layout authority are mandatory. Executable parity remains visible
as a separate reported gap when no safe official calculator or formula workbook
is registered.

The public registry package now exports the audit result and audit function so
CLI, review, and later modelo waves can consume the same backend instead of
recomputing coverage in ad-hoc tests.

The catalogue verification suite now exercises the committed registry through
the new audit gate and fails if any modelo revision loses mandatory legal,
source, or layout coverage.

Review tightened workbook parity tier handling: executable parity and layout
authority workbook refs only satisfy a gate when the workbook source itself has
the matching evidence tier.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_catalogue_verification.py -q`

Result: 31 passed.

`uv run ruff check src/aeat/domain/calculations/registry/_coverage.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_catalogue_verification.py`

`uv run ty check src/aeat/domain/calculations/registry/_coverage.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_catalogue_verification.py`

`git diff --check`
