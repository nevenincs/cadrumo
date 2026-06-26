---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S08'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rename ModeloReconciliationSourceKind to ModeloReconciliationEvidenceKind (reconcile transport / external-evidence axis, NOT folded into BindingSourceKind) as one atomic relocation:ModeloReconciliationSourceKind commit, sweeping all 30 occurrences across the reconcile CLI, the application modelo __init__ re-export, _reconcile.py, _justificante.py, and the two test modules and ## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/modelo/_reconcile.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo_reconcile_cli.py`
- `src/aeat/application/live/_justificante.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
