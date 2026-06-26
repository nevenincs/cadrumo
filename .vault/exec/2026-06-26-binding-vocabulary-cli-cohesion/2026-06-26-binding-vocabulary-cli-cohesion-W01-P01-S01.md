---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S01'
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
     The S01 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Rename BindingRowPayload to BindingListRowPayload as one atomic relocation:BindingRowPayload commit, sweeping the def, __all__, ModeloBindingsListResult.bindings, the _modelo_discovery_cli import, _binding_list_rows_for_report uses, and the test docstring and ## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct deltas in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename BindingRowPayload to BindingListRowPayload as one atomic relocation:BindingRowPayload commit, sweeping the def, __all__, ModeloBindingsListResult.bindings, the _modelo_discovery_cli import, _binding_list_rows_for_report uses, and the test docstring

## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct deltas in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`

## Description

- Rename the CLI bindings-list row payload class from the bare `BindingRowPayload` homonym to the role-distinct `BindingListRowPayload` in `_modelo_payloads.py`.
- Update the `ModeloBindingsListResult.bindings` tuple field annotation and the `__all__` export entry (re-sorted alphabetically, `BindingListRowPayload` before `BindingPreviewRowPayload`).
- Sweep the `_modelo_discovery_cli.py` import and the four `_binding_list_rows_for_report` builder uses (the typed return annotation, the two local variable annotations, and the constructor call).
- Update the `bindings list` payload docstring in `test_modelo_registry_surface.py`.

## Outcome

Landed as one atomic commit `relocation:BindingRowPayload` (`22eec2f85`); 9 insertions / 9 deletions across three files. Same-module rename, so no API-stub or locale deltas were generated. RAG-grounded then grep-confirmed against HEAD `0b5e7926d`; zero residual `BindingRowPayload` references remain in `src/`. Ruff clean, collect-only clean (16461 collected, baseline-equal), apidocs scaffold conformant.

## Notes

The three scoped files carried no peer WIP, so a direct explicit-path stage and verified-index commit were sufficient (no apply-cached drive needed). The illustrative `BindingRowPayload` mention in the generated `binding-values-carry-provenance` rule files is a doc example on a `vaultspec-core sync`-managed surface and is intentionally left untouched.
