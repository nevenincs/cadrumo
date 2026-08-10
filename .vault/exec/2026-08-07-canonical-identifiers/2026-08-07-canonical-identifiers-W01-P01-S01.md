---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:07531079f9c20731e0937a8a1be7fe60afb41e1743fbbec10fe61ad0892fad65'
step_id: 'S01'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Re-read domain/modelos/_ids.py against current HEAD to confirm the four ids and the duplicate pattern are still declared as described here, then alias WorkUnitId, CalculationRevisionId, FilingRecordId and VerificationReportId from core.identity.Hex64Str, deleting the duplicate pattern declaration. HEAD re-read is DONE as of 2026-08-10: all four aliases and the module-local _HEX_64_PATTERN are still declared verbatim, so the duplication this row exists to close is still live. The aliasing itself does not land as its own commit -- it is inseparable from the relocation in S02, so each symbol's alias-and-move share one index per the relocation-atomicity rule

## Scope

- `src/cadrumo/domain/modelos/_ids.py`

## Description

- Alias `WorkUnitId`, `CalculationRevisionId`, `FilingRecordId` and `VerificationReportId` from the shared hex-64 primitive in the identity facade.
- Delete the module-local duplicate pattern declaration that each alias had been constrained by.
- Land no commit of its own: per this row's own text the aliasing is inseparable from the relocation, so each symbol's alias-and-move shared one index.

## Outcome

Delivered, inside the four relocation commits rather than separately, which is what the row
specified. `ff158aa2b1` carried `VerificationReportId`, `dca2ff589a` `FilingRecordId`,
`5f8c0504f8` `CalculationRevisionId` and `e31ef6337f` `WorkUnitId`. The duplicate pattern
constant went with the module that held it.

**THIS RECORD IS RECONSTRUCTED POST-HOC AND ITS AUTHOR DID NOT DO THE WORK.** It was written
on 2026-08-11 by the identity lane from the landed commits and from a census taken at HEAD,
not from the executing agent's own account, which did not survive its session. Every claim
here is a property of the tree that anyone can re-measure; none of it is testimony.

Verified at HEAD by an AST census over the git object store rather than a line grep, because
a line grep cannot see a multi-line `from x import (` and that exact instrument once reported
zero broken consumers here against a real 195. All four symbols: exactly one declaration site
each, all four in the identity facade's `__all__`, and zero residue in the old modelos facade.

## Notes

The row's premise was still live when the work ran and is now spent: it instructed a HEAD
re-read to confirm the four aliases and the module-local pattern were still declared. They
were, they no longer are, and the module that held them is gone.

**A caution for anyone reading this row's siblings as open.** This record exists because the
plan under-reported: the work landed on 2026-08-10 and the row still read unchecked on
2026-08-11, which invited a second agent to redo it. A plan that under-reports is not the
harmless direction it appears to be.
