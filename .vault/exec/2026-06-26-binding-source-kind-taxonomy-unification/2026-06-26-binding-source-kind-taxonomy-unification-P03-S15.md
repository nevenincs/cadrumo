---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Migrate operator_surface SourceKind consumers to BindingSourceKind and delete the duplicate

## Scope

- `src/aeat/application/operator_surface/_models.py`

## Description

- Reconcile `P03.S15` as the operator-surface `SourceKind` retirement row.
- Record the original landing in `b5b28a86aa`: delete the duplicate operator
  `SourceKind`, migrate `SourceKindAlias.canonical`, contract `source_kinds`,
  `SOURCE_KINDS`, `SOURCE_KIND_ALIASES`, `resolve_source_kind_alias`, and the
  package re-export to `BindingSourceKind`.
- Confirm the current tree has no `class SourceKind` definition and the
  operator surface contract exposes canonical `BindingSourceKind` members plus
  input-only aliases.

## Outcome

The checked row now has its own exec record. The existing P03 evidence records
the duplicate-enum deletion complete with 1032 targeted tests green, registry
loads clean, both parity halves green, and clean collection.

## Notes

No code changed in this reconciliation. `SourceKindAlias` remains by design as
an input-only alias model, not a source-kind enum.
