---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Rename ModeloReconciliationSourceKind to ModeloReconciliationEvidenceKind (reconcile transport / external-evidence axis, NOT folded into BindingSourceKind) as one atomic relocation:ModeloReconciliationSourceKind commit, sweeping all 30 occurrences across the reconcile CLI, the application modelo __init__ re-export, _reconcile.py, _justificante.py, and the two test modules

## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/modelo/_reconcile.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo_reconcile_cli.py`
- `src/aeat/application/live/_justificante.py`

## Description

- Rename the reconcile-transport source-kind enum from the `SourceKind` homonym to `ModeloReconciliationEvidenceKind` (the external-evidence axis: justificante or declaration).
- Sweep all 30 occurrences across the reconcile CLI, the application modelo package `__init__` re-export (import + `__all__`, repositioned alphabetically), the `_reconcile` def / four command source-kind fields / two DECLARATION comparisons / dispatcher param / history-decode constructor / `__all__`, the live justificante reconcile path, and the two reconcile test modules.
- Keep the member string values (`justificante`, `declaration`) unchanged; type rename only.

## Outcome

Landed as one atomic commit `relocation:ModeloReconciliationSourceKind` (`820498740`). The axis is NOT folded into `BindingSourceKind` (it is a distinct external-evidence axis). collect-only clean, ruff clean, the 15 reconcile and reconciliation-history tests green.

## Notes

Two scoped files (`_reconcile.py` and the modelo package `__init__`) carried live peer WIP: an `_evidence_invalid_refusal` source-ref enrichment and a `derive_taxpayer_files_economic_activity` `__all__` reorder. Both renames were staged via the apply-cached own-only drive (HEAD-anchored own-only patches built with the rename plus the alphabetical `__all__`/import reposition, `git apply --cached`, zero-foreign-marker verification, no-pathspec verified-index commit). The peer WIP was preserved intact (verified post-commit: the refusal enrichment and the `derive_taxpayer` reorder both still present in the working tree).
