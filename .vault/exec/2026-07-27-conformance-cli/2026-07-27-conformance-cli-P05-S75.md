---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S75'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# correct the two step records that misstate their own state, one claiming this campaign left the tree-wide gates clear and one closing while its stated precondition had not landed

## Scope

- `.vault/exec`

## Description

- Correct the record claiming this campaign left its half of the gates clear.
- Name the leak it missed and why the triage could not have seen it.
- Correct the record that closed without one of its stated preconditions.
- Record why proceeding was safe and what the residual is.
- Leave both Steps closed; only the prose was wrong.

## Outcome

Both records now state what they should have stated originally, as corrections
carrying their own heading rather than as silent rewrites. A record that is
quietly edited to be right loses the fact that it was wrong, and that fact is
the part a later reader needs.

The verification record claimed "this campaign's half of that gate is clear"
while the repository-wide privacy lint was red on eight lines of this campaign's
own conformance CLI test module. The correction names the leak, states that it
was owner-caused and outstanding at the time, and states that it was not among
the five regressions the record enumerates as absorbed. It also records why the
triage could not have found it, which is the durable part: the scoped suites were
selected by the trees the campaign EDITED, the privacy gate lives in a different
tree and scans the whole repository, and the full-tree gate that did run was
collect-only and asserts nothing. A tree-wide gate that reads a file you changed
has no route into a triage keyed on where you changed it.

The attribution record closed a Step whose own row conditioned it on two
preconditions, only one of which had landed. The correction names the missing
one, records that it is now tracked separately, and gives the reason proceeding
was nonetheless safe — a reason the record already evidenced without connecting
to the precondition. The preconditions exist so the widening cannot move an
attribution mid-correction, and the widening moved nothing: the full fold was
dumped before and after and the two dumps are byte-identical. A change proven a
no-op against the live corpus cannot be contingent on a correction that has not
happened. The residual is stated rather than left to inference: what the Step
could not prove is that the widening handles the missing grounding once it
exists, and that belongs to the Step landing it.

Neither Step was reopened. In both cases the work is done and the record was
wrong about it, which is a prose defect, not an execution one.

## Notes

Both corrections were kept specific on purpose. The first names the gate, the
count of lines, the ownership, and the structural reason for the miss; the
second names which precondition was missing and what it would have proved. A
softened version — "some gates were still red", "a precondition was outstanding"
— would satisfy the finding while destroying its value, since the point of the
correction is that a reader can check it.

The vault check reports two errors, both pre-existing peer decision records
missing grounding references, and neither in this feature. No record touched
here is flagged.

Editing the verification record produced a line-ending warning on commit: the
working copy now carries CRLF where the committed blob carries LF. That is the
tree-wide terminator drift already tracked as its own Step; the committed bytes
are correct and nothing was done about the working copy here.
