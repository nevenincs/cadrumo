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




# Re-express CounterpartSourceKind, COUNTERPART_SOURCE_KINDS, and counterpart_source_kind as a derived subset of BindingSourceKind

## Scope

- `src/aeat/core/aggregation.py`

## Description


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


`core/__init__.py` carried unrelated peer `result_disposition_casilla_ids` WIP; the
`AggregationSourceKind` re-export removal landed via the apply-cached gated drive
(own-only hunks staged, foreign-marker verified, no-pathspec commit), leaving the
peer WIP intact in the working tree.

Peer-owned full-tree failure recorded, NOT fixed (owner-triage): the
docstring-core-struct gate fails on `aeat.application.aggregation._withholding_source`
— an UNTRACKED r2 withholding-build module missing a `:class:`ModeloRevision``
docstring link. It is outside this feature's surface; r2 owns the fix.
