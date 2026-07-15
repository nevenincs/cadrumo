---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S439'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Migrate the peer-owned prorrata test's CalculationSourceDiagnostic import to its existing application aggregation facade and rerun the import-hygiene gate after the WIP owner surface is stable.

## Scope

- `src/aeat/application/modelo/tests/test_prorrata_especial_mandatory_live_emit.py src/aeat/application/aggregation/__init__.py`

## Description

- Confirmed the previously peer-owned prorrata test surface was clean and that `CalculationSourceDiagnostic` already has a public application aggregation facade.
- Migrated the test's sole private diagnostic import to that public facade.
- Ran the focused live prorrata suite, full import-hygiene gate, owned Ruff, and scoped whitespace verification.

## Outcome

- The peer-WIP boundary import now uses the existing public facade without an API addition or test-only export.
- The focused live prorrata suite passed 8 tests in 16.05 seconds; the import-hygiene gate passed 11 tests in 43.91 seconds.
- Owned Ruff and whitespace checks passed.

## Notes

- The file was inspected as clean before editing, so the deferred migration did not overwrite active peer work.
