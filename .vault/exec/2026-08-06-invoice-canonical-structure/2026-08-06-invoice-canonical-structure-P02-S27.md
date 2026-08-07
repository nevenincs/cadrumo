---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1ac43f2db75d56a1a8d1f398c92121d7f1b13d2a1a545dbaf370e8d616bace70'
step_id: 'S27'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Make the recargo figure reachable at the confirm boundary and on the persisted invoice once the llm-package-split lane lands its draft-side recargo slot at W02.P04.S79, so the printed-total discrepancy that lane's reader already detects has somewhere to resolve to, this Step owning only the confirm side and never the draft model

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

- Re-tested the Step's declared cross-lane blocker instead of accepting it.
- Proved the operator can now resolve the printed-total discrepancy the reader detects.
- Asserted both halves of the outcome, not just persistence.

## Outcome

**Closed, and the Step's declared blocker did not hold.**

The plan records `S27` as blocked on the sibling campaign's draft-side recargo slot, with the instruction to record the blocker and move on rather than extend the draft model here. That instruction was right about scope and wrong about the blocker.

The draft-side slot is the **reader** auto-detecting a recargo from the document. The confirm side lets the **operator state** one — and that is exactly the scope the plan assigns this Step: "this Step owning only the confirm side and never the draft model". So the confirm half was independently achievable, and the reader half remains the other lane's, untouched.

The state this closes was already pinned by an existing test: a document totalling 126,20 whose record could hold only 121,00, with the 5,20 recargo reported as a discrepancy the operator had nowhere to resolve. The detector was correct and the surface had no answer for it. Now it does.

**Both halves are asserted, and each guards against a different failure.** Persisting the recargo without clearing the advisory would leave it firing on a now-correct record — a new false positive, and precisely the kind that teaches operators to ignore the alert that matters. Clearing the advisory without persisting the recargo would be worse: the under-declaration would go silent again, which is the defect the advisory was built to expose.

The recargo rides inside the invoice total and the retención outside it, so the record now equals what the document printed.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_draft_printed_total.py -q --no-header
    5 passed in 15.50s

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_cli.py -q --no-header
    578 passed in 39.82s

The pre-existing test asserting the unresolvable discrepancy is left standing and still passes, because it describes the path where the operator does NOT declare the recargo. Both records remain correct: undeclared, the advisory fires; declared, it does not.

## Notes

A blocker recorded in a plan is a claim like any other and decays the same way. This one was accurate as a description of the reader path and wrong as a gate on this Step, and the difference only showed up by attempting the work rather than by re-reading the note.

The sibling lane's item is not absorbed here: a reader that DETECTS a recargo and pre-fills it is still worth having, and remains theirs. What is closed is the operator's ability to resolve the discrepancy at all.
