---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:bde8d1ce049da2f158d85395ed3a0b5cfe0631bcafb46d02e8aa47d84749d66d'
step_id: 'S03'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Re-read domain/invoices/_ids.py against current HEAD, alias InvoiceId from core.identity.Hex64Str, and relocate it with its consumer imports updated in the same commit

## Scope

- `src/cadrumo/domain/invoices/_ids.py`
- `src/cadrumo/domain/invoices/__init__.py`
- `src/cadrumo/core/identity/__init__.py`
- `docs/api/cadrumo.domain.invoices._ids.rst`

## Description

- Declare `InvoiceId` in the identity facade from the shared hex-64 primitive and export it.
- Drop it from the invoice package's import line and `__all__`, with no forwarding alias.
- Repoint both consumers, the invoice model and the CLI catalogue payload.
- Move the alias's test to the identity package, because ownership moves with the symbol.
- Delete the emptied source module and remove its orphaned documentation stub.

## Outcome

The relocation is complete and correct at `HEAD`. `InvoiceId` is declared once, in
`core/identity`, exported from the facade, and both consumers reach it there. Nothing
anywhere still imports the deleted module, and the moved test collects at its new path
with the same two cases it carried at the old one.

Verified through an arbiter chosen for this shape rather than a count: zero collection
ERROR lines naming any file in the set, zero references to the removed module, the moved
test collecting exactly two at its new location and zero at the old, lint and format
clean file-scoped, and 309 focused tests passing across both affected test packages.

A differential collection denominator was deliberately NOT used as the verdict. A correct
relocation moves that number by zero, and the tree shed 831 dirty entries and advanced
several commits during the verification window, so a zero-delta inference had no signal
above the churn. The error-line reading names the files under change rather than counting
everyone's, which is what made it survive that window.

## Notes

**THE RELOCATION LANDED IN TWO COMMITS, NOT ONE, AND THAT VIOLATES ATOMICITY.** The move,
the consumer repointing, the facade change, the new test and the stub removal landed under
the intended subject. The canonical-site DELETION of the source module and its old test
landed separately, in an unrelated sweep commit. Between the two, the tree briefly held
the alias in both homes while the invoice package had already dropped its export, so the
old module was present but unreachable.

No defect survives at `HEAD` and no consumer was ever broken, because the deletion is
subtractive and everything reaching the symbol had already been repointed. The rule is
still violated: the canonical-site move and its consumer sweep are required to share one
index, and here they did not.

**The cause is mine and it is a technique lesson worth more than the row.** Removing the
module with a staging verb put the deletion in the index immediately, and the commit then
waited on a verification round. Anything sitting in the index is exposed to any peer's
bare commit for exactly as long as it sits there, and in this tree a sweeper runs
regularly. The deletion was taken by the first one that ran.

The correction for the four remaining relocations: build the whole change in the WORKING
TREE, stage nothing until the verification is already in hand, and then stage and commit
in one movement. A file removal is the specific trap, because the natural verb stages as
a side effect where an ordinary edit does not.
