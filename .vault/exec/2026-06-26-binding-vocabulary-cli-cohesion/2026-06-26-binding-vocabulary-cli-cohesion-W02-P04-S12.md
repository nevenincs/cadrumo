---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S12'
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
     The S12 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Rename the PerModeloAggregationProvider role-family to a name that says aggregation provider role (e.g. PerModeloAggregationContributor) for both PerModeloAggregationProvider and PerModeloAggregationProviderContract as one atomic relocation:PerModeloAggregationProvider commit, sweeping the enum, the contract model, the provider field / providers tuple, and the ~12 consumer sites and ## Scope

- `do NOT rename ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions (settled by phase-2.2)`
- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/aggregation/_service.py`
- `src/aeat/application/aggregation/_source_mesh.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename the PerModeloAggregationProvider role-family to a name that says aggregation provider role (e.g. PerModeloAggregationContributor) for both PerModeloAggregationProvider and PerModeloAggregationProviderContract as one atomic relocation:PerModeloAggregationProvider commit, sweeping the enum, the contract model, the provider field / providers tuple, and the ~12 consumer sites

## Scope

- `do NOT rename ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions (settled by phase-2.2)`
- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/aggregation/_service.py`
- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Rename the aggregation provider role-family StrEnum `PerModeloAggregationProvider` to `PerModeloAggregationContributor` and the contract model `PerModeloAggregationProviderContract` to `PerModeloAggregationContributorContract`, so the contributor-role axis is name-distinct from the settled resolver port.
- Sweep `_service.py` (def, contract model, field/param annotations, the readiness and dispatch dicts, the contract builder, `__all__`), the aggregation package `__init__` re-export and module docstring, and the two aggregation-service test modules.
- Keep the StrEnum member string values and the `provider` field / property / `provider_for_modelo` function names unchanged.
- Leave the settled phase-2.2 `ModeloSourceResolver` / `CalculationSourceResolution` / `merge_source_resolutions` contract untouched.

## Outcome

Landed as one atomic commit `relocation:PerModeloAggregationProvider` (`f27a125d7`). collect-only clean, ruff clean (one wrapped over-long assertion line after the longer name, plus alphabetical `__all__`/import repositions), the 32 aggregation-service tests green. The only `ModeloSourceResolver` reference in the commit is a new docstring cross-reference contrasting the contributor role against the settled port; the settled contract itself is not renamed.

## Notes

Scope decision: the `provider` field / property / `provider_for_modelo` function names were intentionally kept (not renamed to `contributor`). The field is internal vocabulary, not the homonym target the plan names, and renaming it risked changing a serialized log/contract key (`as_extra` emits a literal `provider` key), which would break the behaviour-preserving mandate. All four scoped files were clean of peer WIP.
