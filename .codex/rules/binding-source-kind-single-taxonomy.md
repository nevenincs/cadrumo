---
name: binding-source-kind-single-taxonomy
trigger: always_on
---

# Binding source kinds are one canonical core taxonomy

## Rule

The binding `source` closed set MUST be the single canonical `BindingSourceKind`
StrEnum declared in `cadrumo.core`. `DataBindingDefinition.source` is typed as
that enum, and every per-family source-kind collection MUST be **derived** from
it, never hand-maintained as a string-literal list. A new binding source kind is
added to `BindingSourceKind` with its value byte-identical to its stored token,
and a registry-versus-enum parity gate keeps the enum and the registry-declared
source set in lock-step.

## Why

The binding source set was a MIXED Literal — some enum members, some bare
strings — with per-family frozensets hand-listed and disagreeing with it. One
ledger collection carried only half the ledger kinds, so the ledger preflight
misclassified the rest, and a sibling grouping enum's members did not match the
source tokens. One canonical enum with derived collections gives the closed set a
single typed home, makes "is this a ledger binding?" computable rather than
hand-maintained, and makes a new registry source without an enum member fail
loudly.

## How

- **Good:** `DataBindingDefinition.source: BindingSourceKind`; the loader
  hydrates the registry's plain-string token to its member at the boundary.
- **Good:** a family collection built as
  `frozenset(k for k in BindingSourceKind if ...)` — derived from the enum and
  complete by construction.
- **Bad:** a new hand-listed string set for a family, or a mixed enum/string
  Literal on `source`.
- **Bad:** renaming a stored source token to "align" it. The enum VALUE must
  equal the stored token, and `retired-enum-members-need-consumer-reconciliation`
  governs any member move.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision B). Enforced by
`test_binding_source_kind_taxonomy.py`. Companions:
`aeat-architecture-boundaries`, `aeat-schema-central-config`,
`retired-enum-members-need-consumer-reconciliation`.
