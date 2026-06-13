---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S139'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S139 Modelo Amendment and Import Extraction

Scope: extract residual modelo amendment and external filing import workflows behind the modelo application facade.

## Description

- Extracted `amend_modelo_revision` into `src/aeat/application/modelo/_amendment_actions.py`.
- Extracted `import_external_filing_evidence` into `src/aeat/application/modelo/_external_import_actions.py`.
- Split amendment baseline loading/validation into `_load_amendment_baseline`.
- Split external import target validation/loading into `_load_external_import_target`.
- Split export draft approval into `_approve_export_draft` so the adjacent export callable also stays under the hard callable budget.
- Kept `src/aeat/application/modelo/_actions.py` as the private compatibility facade and `aeat.application.modelo` as the public consumer facade.
- Preserved amendment evidence gates, override validation, filed-record supersession, imported AEAT evidence custody, and bucket-event emission in the application layer.

## Outcome

The residual amendment and external import workflows now live in focused modules behind the existing facades. The modelo action root is reduced to a compatibility shim over work lifecycle, calculation, verification, filing, amendment, and import helpers.

Final callable sizes after the residual split:

- `verify_modelo_revision`: 152 lines.
- `amend_modelo_revision`: 153 lines.
- `import_external_filing_evidence`: 162 lines.
- `export_modelo_revision`: 175 lines.

## Notes

The file-flow fixture now persists real justificante metadata for imported AEAT justificante evidence so the clean-state guard can verify evidence references instead of accepting dangling CSV-like identifiers.
