---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S01'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The add a BindingAggregationOp StrEnum and a typed BindingAggregation pydantic model in core, then wire the typed aggregation field onto DataBindingDefinition replacing the free-form mapping and ## Scope

- `src/aeat/core/aggregation.py`
- `src/aeat/domain/calculations/registry/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add a BindingAggregationOp StrEnum and a typed BindingAggregation pydantic model in core, then wire the typed aggregation field onto DataBindingDefinition replacing the free-form mapping

## Scope

- `src/aeat/core/aggregation.py`
- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Enumerate the complete binding aggregation op set from the registry authoring tree by sweeping every binding-table `aggregation = { op = "..." }` declaration; confirm the closed set is sum, rows, copy, count_distinct, prior_pagos_fraccionados.
- Add a `BindingAggregationOp` StrEnum to `aeat.core.aggregation` carrying exactly those five members, sited alongside `AggregationSourceKind` as the cross-layer home.
- Add a strict, frozen `BindingAggregation` pydantic model carrying a single `op` field of that enum, with a before-validator that hydrates the raw TOML op string into its member at the boundary so the authoring tree stays plain while an unknown op is rejected.
- Retype `DataBindingDefinition.aggregation` from the free-form `Mapping[str, str | int | DecimalValue | bool] | None` to `BindingAggregation | None`, deleting the untyped shape rather than bridging it.
- Promote `BindingAggregationOp` through the registry package `__all__` re-export surface.

## Outcome

- The free-form aggregation mapping is gone from the schema; the loader compiles each TOML aggregation table into the typed `BindingAggregation` via the existing pydantic validation path, so an unknown op or stray extra key now fails at registry-build validation.
- The confirmed op set matched the pre-existing enum draft exactly; no registry TOML required an op addition.

## Notes

- A substantial coherent draft of S01 and S02 was already present as uncommitted working-tree state on the shared branch (the enum, model, schema retype, accessor module, and the production re-parse replacements). Each file was diff-inspected and confirmed to map one-to-one onto the P01 scope fence before continuing, per the abort-on-WIP discipline; the work was extended rather than re-authored.
- Scope fence held: relation aggregation and formula-expression op axes were left untouched.
