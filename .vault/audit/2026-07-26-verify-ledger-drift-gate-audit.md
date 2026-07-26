---
tags:
  - '#audit'
  - '#verify-ledger-drift-gate'
date: '2026-07-26'
modified: '2026-07-26'
related: []
---

# `verify-ledger-drift-gate` audit: `verify-time ledger drift on BORRADOR drafts`

## Scope

The verify-time behaviour of a BORRADOR calculation revision whose contributing
ledger rows changed after it was calculated. Opened as the first of three
operator-approved follow-ons to the deductible-evidence promotion, which routes
operators onto exactly this path. Closed in the same pass rather than left as a
finding, because it is an over-declaration route rather than a reporting gap.

## Findings

### The evidence gate and the casilla values read two different worlds

Verify targets the work unit's current calculation revision. The deductible
evidence gate loads the LIVE transaction catalogue, while the casilla values
under audit come from the STORED revision. Those are the same world only while
nothing changes in between, and nothing enforced that.

The reachable sequence: an operator meets the blocking deductible-evidence
finding, reclassifies the row to drop the deduction rather than attaching an
invoice, and re-runs verify without recalculating. No recalculate means the work
unit still points at the same draft. The evidence gate reads the live ledger,
sees a row that is no longer deductible, and raises nothing. The casilla values
still assert the deduction. The verify grants, and the grant freezes an evidence
bundle over values the ledger no longer supports.

This was reproduced rather than argued. Unwiring the new gate and re-running the
operator sequence makes the assertion on the refusal fail with
`assert True is False` on `granted_verificado_completo` — the stale draft grants.

The finding's own next_action contributed: it said "then rerun verification",
which is correct for the attach route and wrong for the reclassify route. The
wrong order was never refused, so nothing corrected the operator afterwards.

### A never-granted draft had no anchor to compare against

The ledger snapshot was captured only inside the `if granted:` branch of verify,
so the drafts that needed guarding were exactly the drafts with nothing stored to
compare. The fingerprint machinery and its staleness evaluator already shipped;
they were scoped to finalized revisions and skipped drafts entirely.

### The anchor's discrimination is the whole design, and it holds

A fingerprint-anchored gate is only viable if the fingerprint moves for a
reclassify and stays put for an evidence attach. Catching an attach would refuse
the very recovery the deductible-evidence promotion instructs, breaking the path
the promotion depends on.

The fingerprint covers tax facts only and carries no attachment identifiers,
which suggests the answer but does not settle it: `lifecycle_state` IS one of the
fingerprinted facts, so whether the real attach path transitions it is
behavioural. Measured through the production paths end to end: an attach that
genuinely sets the evidence id leaves the fingerprint identical, and a reclassify
moves it.

### Two correct guards made one shipped test's sequence impossible

The M210 authority-exclusivity test mutated its only contributing row twice to
exercise the staleness verdicts, then verified the same draft and asserted a
grant. That grant was the defect. Correcting the sequence proved impossible in
place, and instructively so: verifying after the mutations is the stale draft the
new gate refuses, and verifying before them finalizes the revision, after which
the ledger refuses to mutate a row a finalized revision cites.

Both guards are correct and the collision is real, so the assertions were split
rather than weakened. The staleness half stays; the evidence-bundle half moved to
its own test on a revision whose ledger never moves. No coverage was dropped.

## Recommendations

The gate is implemented, so these record what was decided rather than what remains.

**A ledger-derived draft with no anchor is refused, not passed.** It was
calculated before the anchor existed, so whether its values still match the
ledger is unknown, and an unknown is not a pass. Both branches resolve to the
same operator move, so both carry the same instruction. Under the pre-release
regime the only such drafts are local, and recalculating clears them.

**The refusal never recomputes.** A verify that quietly recalculated would mint
values the operator never saw and file them under a report they never read. It
refuses and names the recalculate.

**The refusal names calculate, never verify.** A refusal that names the command
the operator just ran restates their position instead of resolving it. The
evidence finding's next_action now splits its two routes explicitly, because they
do not share a next step: attach is value-neutral so re-verifying is right, while
reclassify needs a recalculate first.

**The message carries counts, not a joined identifier list.** A finding message
is capped at 500 characters and a contributor set is unbounded — the same shape
found six times across the bucket-event payloads. The identifiers are recoverable
from the recalculate the refusal instructs.

**Left open, deliberately.** The export evidence gate accepts a present ledger
snapshot in place of a bundled evidence record. Storing snapshots on drafts does
not reach it — export refuses a draft state first, and the grant path always
writes evidence alongside the snapshot — but the substitution is a pre-existing
looseness worth a later look. Not touched here.

**Practice worth keeping.** Both this gate and the payload-bounding gate landed
the same week were found to have a false green only by making the production code
wrong on purpose and checking the gate noticed. A new gate is unproven until it
has been shown to bite on a deliberate regression of the thing it guards.

## Notes

Semantic discovery was unavailable throughout. The code index is truncated while
reporting itself healthy, and probes expired repeatedly against a service
reporting itself degraded with active index jobs. It was not restarted. Every
statement here rests on reading the owning modules directly, on targeted pattern
search against the current tree, and on measurements run through the production
paths.

The one sweep failure was checked for ownership rather than assumed: it passed
against the HEAD content of the three modules this work changed and failed
against the working tree, which attributed it here rather than to a peer.
