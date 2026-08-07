---
name: binding-source-kind-single-taxonomy
trigger: always_on
---

# Binding source kinds are one canonical core taxonomy

The binding `source` closed set MUST be the single canonical `BindingSourceKind`
StrEnum declared in `cadrumo.core`. `DataBindingDefinition.source` is typed as
that enum, and every per-family source-kind collection MUST be **derived** from
it, never hand-maintained as a string-literal list. A new binding source kind is
added to the enum with its value byte-identical to its stored token, and a
registry-versus-enum parity gate keeps the enum and the registry-declared source
set in lock-step.

The source set was previously a MIXED Literal — some enum members, some bare
strings — with per-family frozensets hand-listed and disagreeing with it: one
ledger collection carried only half the ledger kinds, so the ledger preflight
misclassified the rest.

## How

- **Good:** `frozenset(k for k in BindingSourceKind if ...)` — derived from the
  enum and complete by construction.
- **Bad:** a new hand-listed string set for a family, or a mixed enum/string
  Literal on `source`.
- **Bad:** renaming a stored source token to "align" it. The enum VALUE must
  equal the stored token, and `aeat-quality-gates`
  (now folded into `aeat-quality-gates`) governs any member move.

Full binding contract: `binding-validation-single-contract`. Source: ADR
`2026-06-14-bindings-interface-hardening-adr` (decision B); gate
`test_binding_source_kind_taxonomy.py`.
