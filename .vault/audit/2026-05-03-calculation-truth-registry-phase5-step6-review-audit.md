---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step6-exec]]'
---



# `calculation-truth-registry` Code Review

CALC-REG-008 | HIGH | Filing validator retained model-specific 303/390 calculation authority

Resolved. The filing validator no longer accepts `quarterly_303_drafts`, no
longer runs quarterly reconciliation, and no longer contains the hardcoded
Modelo 390 to Modelo 303 casilla map, Modelo 303 VAT-rate triples,
reconciliation tolerance, or numeric helper used only for that runtime.

CALC-REG-009 | MEDIUM | Application filing export gate did not explicitly block `FilingBuilder`

Resolved. The application package no longer imports or exports
`FilingBuilder`, and the deletion-gate test checks both runtime attributes and
`__all__`.

CALC-REG-010 | INFO | Legacy builder package deletion complete for scoped files

Review confirmed that `src/aeat/domain/filing/_builder.py` and
`src/aeat/domain/filing/_builders/**` are deleted, no remaining runtime imports
target them, and direct import specs are absent.

Post-fix verification:

- `uv run --no-sync ruff check src\aeat\domain\filing src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\domain\filing src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing src\aeat\entrypoints\cli\filing\test_filing_cli.py`

Result: static checks passed; filing slice passed 206 tests with 4 pre-existing
skipped reconciliation tests. Follow-up review reported no remaining findings.
