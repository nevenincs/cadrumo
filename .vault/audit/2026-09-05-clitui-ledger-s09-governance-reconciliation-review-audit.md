---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:793a289494e74a9d5bd62174d84894ab621a656e4da44c6438bdeb2bb8f53b5a'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-04-clitui-ledger-W01-P03-S09]]"
---

# `clitui-ledger` audit: `S09 governance reconciliation review`

## Scope

Reviewed S09's reconciliation of the live predecessor TUI plan against the
clitui-ledger ownership and implementation hold. The review inspected the four
named commits, predecessor and campaign plans, S09 execution record, current
reference and generated indexes, then independently counted dispositions and
checkboxes and challenged removal, duplication, reclassification, and target
mapping behavior. Vaultspec-RAG was attempted first; the local vault index
returned no results, so exact source reads and mechanical census checks supplied
the evidence.

## Findings

**Ruling: NOT ACCEPTED.** Two HIGH findings remain.

The live predecessor plan contains exactly 33 disposition annotations: 27
checked `RETAINED_PREDECESSOR_EVIDENCE` rows, the open S73
`RETAINED_RETIRED_PREMISE_MARKER`, and the five open S390, S395, S396, S411,
and S424 `DISPLACED_AND_HELD_UNTIL_G3` rows. Its completion remains 408 of 426
Steps. The mixed rows retain their non-Ledger scope, S73 remains explicitly
open without claiming parity implementation, S09 is checked, S10 is next, and
G0 remains OPEN. Commit inspection found documentation and index changes only;
no production or TUI implementation was introduced.

### disposition-census-has-no-detector | high | Sole ownership and hold annotations can silently drift

No production, development, or test code parses `CLITUI_LEDGER_DISPOSITION`.
The exact 33-row population, the three allowed tokens, the required checkbox
state for each token, the known overlap identities, and the one-token-per-row
rule exist only as prose in the predecessor plan. Removing an annotation,
duplicating one, applying an unknown token, changing a retained row to
displaced, or introducing a new Ledger-overlapping row without annotation is
not rejected by a campaign-specific detector; the generic Vault checks remain
green. That makes the sole-owner and G3 hold boundary silently
under-declarable.

### s411-target-is-the-record-step-not-the-navigation-owner | high | Substantive selection handoff is routed to the wrong campaign Step

S411 says its unresolved remainder is navigation: carry a selected transaction
from entries or review into classification and return a prepared import to its
area. Its annotation points to `W05.P19.S128`, which only records the reconciled
disposition of held predecessor rows before work resumes. The exact
implementation owner is `W05.P21.S136`, whose text carries selected
transaction, prepared import, review change-set, and artifact-plan identities
through Ledger navigation. The current pointer therefore sends substantive
work back to a governance-record Step and can let the navigation obligation be
missed.

## Recommendations

- Add a focused governance detector under `dev/quality/tests/` that parses the
  predecessor plan and pins the exact 27 retained IDs, open S73 marker, exact
  five displaced IDs, allowed stable tokens, checkbox/token relationships,
  one disposition per overlap, and refusal for missing, duplicate, unknown, or
  unannotated Ledger overlap. Mutation tests must prove each refusal.
- Change S411's clitui-ledger destination to `W05.P21.S136`; retain S128 only as
  the later governance reconciliation checkpoint.
- Re-run the predecessor-plan census and plan/feature Vault checks before
  closing S09 again. Do not change the 408/426 completion state or implement
  any TUI work.

## Verification

The independent census reproduced 33 dispositions as 27 retained, one retired
premise marker, and five displaced-and-held rows, with 408 checked and 18 open
Steps. Named commit inspection confirms the plan mutations were performed by
Vault documentation commits and that S09's record accurately names the shared
worktree commits. Feature Vault checks pass, but there is no focused S09
detector to run; that absence is the first HIGH finding rather than positive
evidence.
