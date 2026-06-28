---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S05'
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
     The S05 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-high-executor: collapse RegistryRelationSourceRequirement and RegistryModeloObservationRequirement onto one typed requirement model with one period-offset field, atomic relocation:RegistryFoldRequirement with consumers and top-level __all__ re-export and ## Scope

- `src/aeat/domain/calculations/registry/_relations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-high-executor: collapse RegistryRelationSourceRequirement and RegistryModeloObservationRequirement onto one typed requirement model with one period-offset field, atomic relocation:RegistryFoldRequirement with consumers and top-level __all__ re-export

## Scope

- `src/aeat/domain/calculations/registry/_relations.py`

## Description

- Introduce the unified `RegistryFoldRequirement` model in `_relations.py`, carrying the superset of the two prior records' fields with BOTH the source-period axis (`periods`) and the source-casilla axis (`source_casilla_ids`) as plural tuples; preserve the build-time uniqueness validator on `binding_ids` / `source_casilla_ids`.
- Delete `RegistryRelationSourceRequirement` (was singular `source_casilla_id`) and `RegistryModeloObservationRequirement` (was singular `period`).
- Rewire the relation producer `relation_source_requirements` to emit `source_casilla_ids=(source_casilla_id,)` while keeping plural `periods`; rewire the previous-filing producer `previous_filing_observation_requirements` to emit `periods=(required_period,)` and `filing_periods` as a tuple while keeping plural `source_casilla_ids`.
- Guard the `RegistryModeloObservation` type-only import in `_relations.py` under `TYPE_CHECKING` to break the module-load cycle the new `_bindings_previous_filing` to `_relations` edge would otherwise introduce.
- Re-export `RegistryFoldRequirement` once through the registry package, removing the two old names from `_bindings.py` and the package `__init__` import and `__all__` blocks.
- Migrate every consumer atomically to the merged shape: the two clean-state-gate mappers, the relation-prefill and binding-prefill walks, the sede declarations production capture loop, and all requirement-field assertions across the registry, application, and sede test surfaces. Single-cardinality reads become `source_modelo` (was `modelo`), `periods[0]` (was `period`), and `source_casilla_ids[0]` (was `source_casilla_id`).

## Outcome

- One atomic relocation commit `e3975640e` (`relocation:RegistryFoldRequirement`), 19 files, value-preserving by construction: only the record TYPE unified, no casilla value shifted.
- No-shift evidence: the full calculations and registry test suites passed (3253 tests); the named carry-regression gates passed (44 tests covering M303 refunded-period zero-carry, M390 box 97/662 FIFO carry, pull-vs-calculate parity, cross-period clean-state); the sede declarations and cross-period gate suites passed (49 tests); `pytest --collect-only` collected cleanly (16461 tests, unchanged from baseline). All migrated requirement-field surfaces are green.
- The relocation honoured the shared-worktree apply-cached discipline: three target files carried live peer WIP (a docstring tweak, the codex casilla-id rename sweep, a type-annotation addition). Each was staged through a HEAD-anchored own-only patch via `git apply --cached`; the staged index was verified to carry zero foreign peer markers immediately before the no-pathspec commit, and the peer WIP remains intact and uncommitted in the working tree after the commit.

## Notes

- The originating brief instructed preserving the previous-filing record's SINGULAR `period`, but the relation record genuinely fans a PLURAL `periods` tuple (the annual M100 fold over 1T..4T), pinned by existing tests in two contradictory directions. This was surfaced as a design-ambiguity stop; the coordinator ruled the behaviour-preserving superset merge (both axes plural, each producer emitting single-element tuples where its cardinality is one). Option B (restructuring the relation producer to one record per period) was rejected as a produced-record cardinality change, contradicting the relation-prefill source-mesh scoping test.
- Several requirement-field consumers were outside the reference anchor table (the sede declarations production capture loop, the binding-prefill grouping walks, and multiple per-modelo registry tests). All were discovered and migrated in the same atomic commit so collection stayed clean; none were deferred.
