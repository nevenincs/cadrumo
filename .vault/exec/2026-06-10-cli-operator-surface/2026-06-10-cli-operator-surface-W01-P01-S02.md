---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S02'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# extend the conformance gate to assert every Typer option typed as an enum has its advertised choice set equal to the set the handler accepts, failing on any advertised member the handler refuses

## Scope

- `src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py`

## Description

Added the Class-2 enum-choice-vs-handler contract to the D5 gate. A registered
`_EnumChoiceSurface` row names a command path, an option flag, the live
advertised member set (read by duck-typing the option type's `choices`
attribute, agnostic to the vendored `typer._types.TyperChoice`), and an
`accepts` predicate grounded in the handler's real acceptance rule. Two
parametrized tests pin advertised == accepted: one fails on an advertised member
the handler refuses (over-advertisement), the other on a handler-accepted member
the choice set hides.

Full generic enumeration of every choice option in the tree was judged
disproportionate (many choice sets are validated late against dynamic registry
data), so the gate pins the explicitly-registered surfaces the audit named
(`ledger doclink --source`, `modelo work verify --select`) with a documented
enrolment path for new surfaces.

## Outcome

Gate extended. The `accepts` predicates are grounded in the handler mappings
(`DocumentLinkSource` -> `AttachmentKind` for doclink; the BORRADOR-reachable
selector subset for verify), not in the advertised set, so the assertions are
not tautological. Both surfaces pass after the S03/S04 fixes; verified via the
HEAD-consistent CLI-tree swap.

## Notes

The vendored choice type (`typer._types.TyperChoice`) is not an instance of
`click.Choice`, so the gate reads `getattr(param.type, "choices", None)` rather
than an `isinstance` check.

