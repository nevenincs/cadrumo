---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S13'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-source-kind-taxonomy-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-06-26-binding-source-kind-taxonomy-unification-plan placeholders are machine-filled by
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
     The Re-express CounterpartSourceKind, COUNTERPART_SOURCE_KINDS, and counterpart_source_kind as a derived subset of BindingSourceKind and ## Scope

- `src/aeat/core/aggregation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-express CounterpartSourceKind, COUNTERPART_SOURCE_KINDS, and counterpart_source_kind as a derived subset of BindingSourceKind

## Scope

- `src/aeat/core/aggregation.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

This record covers all of P03 (S13 + S14 + S15) — one atomic commit `b5b28a86a`,
reconciliation preceding deletion per the retired-enum-reconciliation rule.

- S13: re-express `CounterpartSourceKind`, `COUNTERPART_SOURCE_KINDS`, and
  `counterpart_source_kind` as a derived subset of `BindingSourceKind`, relocated
  below the enum so the `Literal` / frozenset resolve.
- S14: delete `AggregationSourceKind`; inline the four `BindingSourceKind` member
  values that referenced it; migrate every consumer to `BindingSourceKind` (the
  per-modelo aggregation service, `_retenciones` / `_foreign_assets` canonical
  sets, the registry `_bindings` selector + validator dispatch tables,
  `_counterpart_bindings` default, review `_operator` kind map, ledger
  `_actions_manual`, the core re-export, the aggregation package re-export, and the
  affected gate/inventory tests); delete the now-subjectless canonical-home guard
  `core/tests/test_aggregation.py`.
- S15: delete `operator_surface.SourceKind`; migrate `SourceKindAlias.canonical`,
  the contract `source_kinds`, `SOURCE_KINDS` / `SOURCE_KIND_ALIASES`,
  `resolve_source_kind_alias`, and the package re-export to `BindingSourceKind`;
  rewrite the S15 reconciliation gate to assert the operator surface mirrors the
  counterpart subset of `BindingSourceKind`, read from the live contract.

## Outcome

P03 complete. 1032 targeted tests green; registry loads clean; both parity halves
green; clean collection. `AggregationSourceKind` and `operator_surface.SourceKind`
no longer exist in the tree (only two intentional docstrings name the deleted
enum). Behaviour-preserving: every migrated member carries the byte-identical
value, no casilla value shifts. `RowSetGroupingKind` untouched (scoped out, no
bridge).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

`core/__init__.py` carried unrelated peer `result_disposition_casilla_ids` WIP; the
`AggregationSourceKind` re-export removal landed via the apply-cached gated drive
(own-only hunks staged, foreign-marker verified, no-pathspec commit), leaving the
peer WIP intact in the working tree.

Peer-owned full-tree failure recorded, NOT fixed (owner-triage): the
docstring-core-struct gate fails on `aeat.application.aggregation._withholding_source`
— an UNTRACKED r2 withholding-build module missing a `:class:`ModeloRevision``
docstring link. It is outside this feature's surface; r2 owns the fix.
