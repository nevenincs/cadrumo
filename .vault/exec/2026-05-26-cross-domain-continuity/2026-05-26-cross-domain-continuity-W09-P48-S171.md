---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:c221159cc834c53ca534b8757a88c8270532324396b341e1840549ec60d022db'
step_id: 'S171'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# dispatch Sonnet drift-verification agent over every Wave-9 touched file fails loudly on remaining duplication shim or re-export

## Scope

- `src/aeat/`

## Description

- Derived the Wave 9 production surface from 208 execution records: 128 named Python modules, 26 registry TOML files, and one stale path reference.
- Used the RAG codebase index to locate period vocabulary, facade exports, dynamic imports, and row-model constant ownership before source-level confirmation.
- Scanned the 128 Python modules for cross-package private imports, compatibility-only modules, private `__all__` exports, and exact AST function clones.
- Reviewed the three dynamic imports in `core.setup_answers`; each targets a sanctioned public domain facade.
- Traced every active `Period.year` consumer and confirmed it is an exact compatibility alias of `filing_year` rather than an independent authority.
- Traced `M347_THRESHOLD_EUR` to its core owner and found five cross-package imports from the private leaf; the domain row model additionally re-exports it.
- Appended S433 and S434 so each remaining drift has one explicit repair owner.

## Outcome

- The named Wave 9 surface has no surviving compatibility-only module, private-export, dynamic-import, or exact-clone violation. The expanded import-boundary review found the M347 private-leaf imports described below.
- Two medium structural drifts remain open: the `Period.year` alias and the five `M347_THRESHOLD_EUR` private-leaf imports, including the domain re-export. They are recorded in the rolling audit and owned by S433 and S434 respectively.
- The stale `access_gate` path is execution-record metadata drift only: the actual module is `core.access_gate`; it is not represented as a production-code defect.

## Notes

- This is a boundary audit, not implementation evidence for S433 or S434. Neither repair is claimed complete here.
