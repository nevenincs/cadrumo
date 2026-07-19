---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S43'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Sweep the storage facade and generated API docs for the removed override_secret_store export and update the import-hygiene baseline after the seam removal

## Scope

- `src/cadrumo/adapters/persistence/storage/__init__.py`

## Description

Verified the seam sweep was already carried atomically by the P07.S41 relocation commit `009ed60006` (`relocation:override_secret_store`), which deleted the module-global test-double seam via real dependency-injection. Confirmed against the current tree that no code change remained for this step.

- Confirmed the storage package facade `__init__.py` re-exports no `override_*` name; a source-wide grep for `override_secret_store` returns only the intentional AST recurrence gate `test_override_seam_singularity.py`, which cites the deleted name in its docstrings and test fixtures.
- Confirmed the generated API-reference stubs carry no drift: `python -m dev.docs.apidocs scaffold --check` reports "Stub tree is conformant. No drift detected."
- Confirmed the import-hygiene baseline (`dev/import_hygiene_baseline.json`) and test-debt inventory carry no stale `override`/`materialisation` edge, and the ratcheting gate `test_import_hygiene_gate.py` is green.

## Outcome

Step satisfied with no additional code change; the facade, generated docs, and import-hygiene baseline were already reconciled by the atomic relocation commit. Evidence gates run green: `test_import_hygiene_gate.py` (11 passed), `test_override_seam_singularity.py` + `test_materialisation.py` (24 passed), and apidocs `scaffold --check` conformant.

## Notes

No code change was required. Per the plan-closure discipline, this step is a verify-and-close backed by the S41 relocation commit rather than a fresh mutation; the P07.S41/S42 backend seam removal already covered the facade export, apidocs, and baseline in one index.
