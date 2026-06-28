---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-fold-in-carry-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-standard-executor: type RelationDefinition.aggregation as the BindingAggregation plus BindingAggregationOp model, hydrating the registry op token at the loader boundary (report-before-land, abort-on-WIP) and ## Scope

- `src/aeat/domain/calculations/registry/_relations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-standard-executor: type RelationDefinition.aggregation as the BindingAggregation plus BindingAggregationOp model, hydrating the registry op token at the loader boundary (report-before-land, abort-on-WIP)

## Scope

- `src/aeat/domain/calculations/registry/_relations.py`

## Description

- Add the new core `RelationAggregationOp` StrEnum (copy/sum) and the `RelationAggregation` model in `core/aggregation.py`, mirroring `BindingAggregation` with the same string-to-member `_coerce_op` hydration.
- Type `RelationDefinition.aggregation` to `RelationAggregation | None` at `_schema_surfaces.py`; the loader's `ModeloRevision.model_validate` hydrates the TOML mapping into the typed model.
- Bump the registry tree cache schema version so the on-disk registry pickle, keyed on the TOML fingerprint, invalidates for a Python schema-shape change.

## Outcome

- Landed in the single atomic P01 commit `4b3311a02` (`relocation:RelationAggregationOp`). The typed field hydrates end-to-end; an isolated round-trip and the committed-registry build both produce the typed `RelationAggregation`.

## Notes

- The plan named `_relations.py` as the field's home; the field is actually declared in `_schema_surfaces.py` (per reference drift D2), so the typing edit landed there.
- Per the D3 ADR amendment, a NEW `RelationAggregationOp` enum is used, not a reuse of phase-2.1's `BindingAggregationOp` (the two op axes are deliberately separate).
- Root-caused a stale on-disk registry pickle that deserialised the pre-typing dict shape under the new typed field; the cache-version bump is the intended invalidation mechanism.
