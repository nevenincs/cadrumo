---
name: binding-source-kind-single-taxonomy
---

# Binding source kinds are one canonical core taxonomy

## Rule

The binding `source` closed set MUST be the single canonical `BindingSourceKind`
StrEnum declared in `aeat.core`; `DataBindingDefinition.source` is typed as that
enum, and every per-family source-kind collection (the invoice / ledger /
counterpart frozensets) MUST be DERIVED from it, never hand-maintained as a
string-literal list. A new binding source kind is added to `BindingSourceKind`
(value byte-identical to its stored token), and the registry-vs-enum parity gate
keeps the enum and the registry-declared source set in lock-step.

## Why

The discovery found the binding source set was a MIXED Literal (some enum
members, some bare strings) with per-family frozensets hand-listed and disagreeing
with it: `LEDGER_BINDING_SOURCE_KINDS` carried only 2 of the 4 ledger kinds (so
the ledger preflight misclassified OSS / renta-income bindings), and the
`RowSetGroupingKind` members for related-party / atribución / refund did not match
the source tokens. One canonical enum with derived collections makes the closed
set a single typed home, makes "is this a ledger binding?" computable rather than
hand-maintained, and a parity gate makes a new registry source without an enum
member fail loudly. Recorded in ADR `2026-06-14-bindings-interface-hardening-adr`
(decision B); enforced by `test_binding_source_kind_taxonomy.py`.

## How

- **Good:** `DataBindingDefinition.source: BindingSourceKind`; the loader hydrates
  the registry's plain-string token to its member at the boundary.
- **Good:** `LEDGER_BINDING_SOURCE_KINDS = frozenset(k for k in BindingSourceKind if ...)`
  — derived from the enum, complete by construction.
- **Bad:** a new `INVOICE_BINDING_SOURCE_KINDS = {"collectible_invoice", ...}`
  hand-listed string set, or a mixed enum/string Literal on `source`.
- **Bad:** renaming a stored source token to "align" it — the enum VALUE must
  equal the stored token (behaviour-preserving lift), and the
  `retired-enum-members-need-consumer-reconciliation` rule governs any member move.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision B), research
`2026-06-14-bindings-interface-hardening-research` (cluster B). Companion to
`aeat-architecture-boundaries`, `aeat-schema-central-config`,
`retired-enum-members-need-consumer-reconciliation`.
