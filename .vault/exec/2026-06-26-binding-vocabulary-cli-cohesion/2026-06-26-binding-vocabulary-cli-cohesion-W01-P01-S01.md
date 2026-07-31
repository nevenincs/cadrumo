---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:cd34aca4c0d74184d6b86bea616a97edcb63af16df832b7bef84b60eb6212b80'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

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
