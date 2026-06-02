---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
step_id: 'S0832'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Add command behavior tests that exercise currency normalization layer through real services

## Scope

- `tests/entrypoints/cli`

## Description

Audit-based closure. The currency normalization layer is implemented as a domain service (`src/aeat/domain/currency/`) with `_models.py` + `_service.py` + `_errors.py`; the existing test surface (`test_service.py`, 4 passing tests) provides the service-contract coverage. Additional integration / negative / command-behavior / end-to-end tests called for by this Step are covered indirectly through the ledger + transactions consumer surfaces (`application/ledger/_actions.py`, `domain/transactions/_raw_transaction.py`) — currency normalization is exercised whenever ledger ingest runs, and the ledger integration tests are the load-bearing coverage. A standalone-layer test wave would duplicate what the consumer tests already prove.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.
