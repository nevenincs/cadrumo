---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S02'
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
     The S02 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Rename ModeloBindingRow to ModeloBindingQueryRow as one atomic relocation:ModeloBindingRow commit, sweeping the def, the rows tuple field, the _binding_rows builder, registry __all__, the registry package __init__ re-export, and the _schema.py docstring-core-struct xref and ## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_queries.py`
- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/domain/calculations/registry/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename ModeloBindingRow to ModeloBindingQueryRow as one atomic relocation:ModeloBindingRow commit, sweeping the def, the rows tuple field, the _binding_rows builder, registry __all__, the registry package __init__ re-export, and the _schema.py docstring-core-struct xref

## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_queries.py`
- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Rename the registry-query binding row projection class from the bare `ModeloBindingRow` homonym to the role-distinct `ModeloBindingQueryRow` in `_queries.py`.
- Update the `ModeloBindingsReport.rows` tuple field, the `_binding_rows` builder return annotation and constructor call, and the `_queries` `__all__` entry.
- Sweep the registry package `__init__` import and `__all__` re-export.
- Update the `:class:` docstring cross-reference in `_schema.py` so the docstring-core-struct graph stays navigable.

## Outcome

Landed as one atomic commit `relocation:ModeloBindingRow` (`acfcbdd90`); 8 insertions / 8 deletions across three files. Same-package rename, so no API-stub or locale deltas. Zero residual `ModeloBindingRow` references remain in `src/`. Bindings-framework gate suite green (98), docstring-core-struct gate green (3), collect-only clean (16461), ruff clean, apidocs scaffold conformant.

## Notes

The registry package `__init__` carried live peer WIP (an unrelated `casilla_metadata_alias` to `casilla_noncanonical_reference` rename plus line-ending normalisations). The two `ModeloBindingRow` re-export hunks were staged via the apply-cached own-only drive: a HEAD-anchored own-only patch built from `git show HEAD:__init__.py`, then `git apply --cached`, with the staged set verified to carry zero foreign markers before a no-pathspec verified-index commit. The peer WIP was preserved intact in the working tree (confirmed post-commit: four `casilla_noncanonical_reference` occurrences still present, zero `ModeloBindingRow`).
