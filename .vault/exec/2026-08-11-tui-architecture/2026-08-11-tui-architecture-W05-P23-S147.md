---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:b0169a82ae00596aa0bd646d43b02825c025639b3f7fe2ac5a33321a387620e9'
step_id: 'S147'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Produce and validate the exact clean-commit TuiOperationFinancialOperandDependencyReceiptV1 with protocol and schema fingerprints, custody-state evidence, crash matrix, non-retention proof, production definition inventory, source ancestry, and the precise edit path it opens

## Scope

- `.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`

## Changes

- `A` `.vault/reference/2026-08-28-tui-architecture-operation-financial-operand-dependency-receipt-reference.md`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py -m unit -n0` -> `pass`
- `verify:` `git status --porcelain -- <the nine enumerated evidence paths>` -> `pass`
- `verify:` `uv run --no-sync vaultspec-core vault check all` -> `pass`

## Notes

The receipt makes a path-scoped ancestry claim rather than a whole-tree one.
It enumerates nine evidence paths with their blob digests, verified clean at
the stamped head immediately before minting, and records both verification
commands so it is reproducible rather than asserted. A whole-repository
cleanliness requirement would make minting impossible in a shared worktree
without making the receipt any more truthful, and an unscoped claim decays
the moment anyone commits, which is how two divergent receipts for one
subject came to exist elsewhere in this feature. The Workspace C2 validator
independently arrived at the same design with the same reasoning recorded in
its own docstring.

One claim in the receipt is explicitly limited. The production definition
inventory is read from the Modelo operation definitions module, which carried
unrelated in-flight work at mint time and could not be attested clean. It was
excluded from the digest table, the inventory is stated as a claim about the
committed head rather than the working tree, and the sole operand declaration
was confirmed byte-identical between head and working copy before the figure
was recorded.

The validator's load-bearing assertions were proven capable of failing before
the receipt reported them. The duplicate-authority census reds on an injected
second declaration; non-retention reds independently on a forbidden field
name and, separately, on a `Decimal` annotation under a benign name. The
second direction matters because the name check fires first and would
otherwise mask an annotation check doing nothing.

The filename differs from the one named in the originating row. It was
scaffolded through the owning verb, which dates it at mint time and appends
the type suffix; hand-authored vault filenames are what produced the
divergent receipt pair noted above.

A comment on the manual-override operand declaration was corrected in the
same change. It stated that no executor could reach the broker side because
`OperationExecutorContext` had no accessor for the operand protocol. That
accessor exists and returns `OperationFinancialOperandContextAccess`, so the
prose described a gap that had already been closed. A receipt attesting to a
contract should not certify a tree whose own prose contradicts it.

Discovery ran on grep and direct file reads rather than the semantic search
service, which was unavailable. The tree's import state broke and recovered
three times during this Step.
