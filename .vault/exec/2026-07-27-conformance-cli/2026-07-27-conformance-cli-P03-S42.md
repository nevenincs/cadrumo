---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S42'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# gate the operator backlog rather than the pending backlog by adding a shrink-only ceiling on revisions lacking operator review, so the one number CI protects cannot be moved by an act the tool can perform

## Scope

- `dev/registry/conformance/manager.py`

## Description

- Add `revisions_without_operator_review` to the shrink-only ceilings, counting every
  revision whose declared status is not `operator_reviewed`.
- Compute it as a subtraction from the census rather than a second sum, so a status added
  to the vocabulary later enrols itself in the operator backlog.
- Record on the ceilings model why the review backlog is two counters and which one CI
  protects.
- Seed the committed baseline with that one key at its measured value, leaving every
  other counter as committed.
- Add four tests: the simulated agent-review sweep, the regression the pending census is
  blind to, the real CLI gate flipping on a lowered ceiling, and the seed-at-true-value
  invariant.

## Outcome

### The gated number was the one the tool could move

The ratchet's only review counter read the `pending_review` census alone, and the ceiling
is shrink-only. There was no ceiling on `agent_reviewed` and no floor on
`operator_reviewed`. The stamp verb is DESIGNED to write `agent_reviewed` — that is the
whole point of the narrowed vocabulary — so an agent sweeping all ninety revisions drives
the one gated governance counter from 90 to 0 while `audit --check` stays green
throughout, and not one revision gains a human signoff.

The governing decision's stated rationale for a three-state enum is that the degenerate
two-state shape cannot carry a pending state, so a real three-state vocabulary "makes the
backlog visible instead of laundering it into prose". Collapsing two of the three tiers
into the single gated counter reintroduced that laundering at the only place anything is
enforced. The screens were honest — the census renders all three tiers, and the coverage
axis carries `governance.review_status.operator_reviewed` — but a screen nobody gates on
is not what CI protects.

### The operator backlog is now the gated number

`revisions_without_operator_review` counts every revision whose declared status is not
`operator_reviewed`. The stamp verb cannot move it at all, which is only true because the
sibling step now enforces the operator-signoff refusal at the writer's function boundary
instead of in its type hints; before that, this counter would have been as movable as the
one it replaces. Agent review remains a real and visible axis — it simply is not progress
against the operator backlog, because it is not the same backlog, and the two counters now
say so separately.

The counter is a subtraction from the census (`revision_count` minus the operator-reviewed
count) rather than a sum over the non-operator tiers. A fourth status added to the
vocabulary tomorrow therefore enrols itself in the operator backlog automatically instead
of silently escaping a hand-listed set.

### The baseline seed, and what was deliberately not swept in

A real `audit --record` to a temporary path measured `revisions_without_operator_review`
at 90 — every revision in the tree, since nothing carries an operator signoff. That single
key was added to the committed baseline at that value. Seeding it anywhere above 90 would
have left headroom for revisions to lose a signoff without the gate noticing, so a test
pins the ceiling equal to the `composed_revisions` floor.

Diffing the fresh measurement against the committed baseline showed one other movement:
the `declared_grounding_claims` floor rose from 58 to 59, which belongs to the peer step
that landed the M303 prorrata percentage as an enforced oracle. A floor RISE is not a
regression and the committed floor still passes, so it was left alone rather than folded
into this edit — capturing a full baseline here would have recorded that step's state
under this step's note. The baseline note records both the seed and the omission.

### Verification

The decisive proof simulates the sweep against the real report through production code
only; the "before this step" column is produced by filtering the violation list to the
counters the ratchet carried previously, so nothing had to be reverted to show the
difference.

```
=== A. the tree as committed ===
ceiling counter=unreviewed_revisions current=90 allowed=90
ceiling counter=revisions_without_operator_review current=90 allowed=90
passed=True

=== B. simulated agent-review sweep across all revisions ===
ceiling counter=unreviewed_revisions current=0 allowed=90
ceiling counter=revisions_without_operator_review current=90 allowed=90
passed=True
the gated pending counter reached zero; no revision gained an operator signoff

=== C. a lost operator signoff, baseline captured at the signed state ===
signed state passes: True
regressed, ceilings BEFORE this step: violations=[] -> would have exited 0
regressed, ceilings AFTER this step:  violations=['revisions_without_operator_review grew from 80 to 81']
regressed passed=False
```

Section C is the assertion that flips. Both states are fully reviewed, so the pending
census is zero on each side and the old counter is structurally blind to the regression;
the new ceiling reds and names the counter that moved. Section B is the shape the finding
described: the act the CLI is designed to allow empties the old gated number and moves the
new one not at all.

The real gate at the amended committed baseline:

```
uv run --no-sync python -m dev.registry.conformance audit --check
audit registry_validated=true passed=true ratchet_violations=0 vacuity_violations=0 baseline_recorded_at=2026-07-27
ceiling counter=unreviewed_revisions current=90 allowed=90
ceiling counter=revisions_without_operator_review current=90 allowed=90
real gate exit=0
```

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
41 passed in 59.46s
```

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 2 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

The test helper that restamps review statuses recomputes the census from the mutated rows
rather than setting the two independently. A fixture whose rows and census disagreed would
let a counter pass while measuring a tree the rows do not describe, which is the shape of
proof this campaign has already had to reject once.
