---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S77'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# rebase the three population-pinned governance ceilings onto ratios or deltas so an honest new revision does not red the only gate and force the operator to assert they are weakening the ratchet

## Scope

- `dev/registry/conformance/manager.py`
- `dev/registry/conformance/cli.py`
- `dev/registry/conformance/conformance-baseline.json`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Move the three review counters and the locale counter out of the shrink-only
  ceilings and into a new grow-only progress family, inverted from work
  outstanding to work done.
- Add the third comparison direction to the audit, the capture guard, and the
  rendered screen, with its own violation kind and its own diagnosis.
- Re-record the committed baseline through the tool and confirm no retained
  counter moved.
- Rewrite the four existing tests that named the retired counters, and widen the
  mixed-movement fixture so direction separation is proved across all three
  families.
- Add four simulations: the arrival, the arrival mid-campaign, the loss, and the
  growth without the loss.

## Outcome

### The ruling: floors on work done, not ratios on work outstanding

The row offered ratios, deltas, or a third capture mode. The answer is none of
those three exactly: a third counter FAMILY, holding the same four quantities
inverted.

The reasoning starts from what the number is. `unreviewed_revisions` is
`population - progress`, and a shrink-only cap on that expression gates whichever
term moves. Both terms move for opposite reasons — a new modelo revision is the
product working, an erased signoff is destroyed evidence — and the counter cannot
tell them apart, so a cap on it must either punish the first or excuse the
second. Splitting the expression is what lets the gate answer the question it can
actually answer.

A RATIO ceiling was the obvious alternative and was rejected on arithmetic rather
than on taste. It works today only by coincidence: the backlog is total, ninety
of ninety unreviewed is a fraction of 1.0, and a ninety-first unreviewed revision
is still 1.0. The choice only surfaces once the campaign makes progress. At forty
of ninety the ceiling fraction is 0.4444; one peer landing an unstamped revision
gives forty-one of ninety-one, 0.4505, which reds. That is the row's own
complaint arriving later and harder to read, and it would fire continuously for
the whole duration of the stamping campaign this surface exists to support. The
test at forty-of-ninety asserts the fraction genuinely falls, so the premise of
this rejection is measured in the suite rather than argued here.

A third CAPTURE MODE was rejected because it puts the judgment in the wrong
place. It would ask the operator, at capture time, to certify "population grew,
backlog fraction did not" — a claim the tool can compute and the operator would
have to eyeball across twelve counters. The counters should be shaped so the
honest capture needs no assertion at all.

What the change gives up, stated plainly: nothing now gates the ARRIVAL of
unstamped revisions. That is deliberate. A gate that reddened on every peer's
registry addition would be routed around within a week, which is worse than an
unenforced fact, and the arrival stays visible on the census and the coverage
screen — which is where an unenforced fact belongs. What is gained is that the
review axis finally has teeth that mean something: before this, an erased
operator signoff on a growing tree could hide inside the ceiling's headroom.

### Three families, three diagnoses

The families are kept distinct rather than folded into the existing floors,
because they fail for different reasons and want different responses. A vacuity
floor falling means the MEASUREMENT shrank, so every counter beside it is
vacuous — which is why it is still reported first. A progress floor falling means
declared work is GONE, and on the review axis that work is underivable by
construction, so nothing in the tree can reconstruct it. A ceiling rising means a
defect count grew, which is a real regression and a fixable one. Collapsing
progress into the vacuity family would have emitted the wrong sentence for the
worst case.

The two-counter split on the review axis survives the inversion intact.
`reviewed_revisions` is the counter the stamp verb is DESIGNED to move — an agent
may write `agent_reviewed` freely — so it is not the counter CI protects.
`operator_reviewed_revisions` cannot be moved by the tool at all, and reads its
census entry directly rather than by subtraction, because for a floor a
subtraction would credit any future review tier with a signoff it does not carry.
`reviewed_revisions` keeps the subtraction for the mirror-image reason: any
revision the census does not call pending has SOME review declared, whatever tier
a later vocabulary adds.

### The baseline transition

The committed baseline could not be re-recorded in place, because the schema
change makes the old file unparseable by the new model and the capture guard
reads the file before comparing. It was captured to a scratch path, installed as
those bytes, and then RE-RECORDED at the committed path with no acceptance flag —
so the artefact that ships was written by the tool, through the guard, and
compared against itself.

Every retained ceiling and floor is unchanged, verified against the old values
printed before the swap. The four new progress values are the exact arithmetic
inverse of the ceilings they replace at this population — reviewed 90-90=0,
operator-reviewed 90-90=0, engineered_by 90-90=0, translated leaves
47376-21609=25767 — so the transition preserves the ratchet's strength rather
than resetting it.

One floor moved: `declared_grounding_claims` rises 58 to 59. That is committed
work, the M303 prorrata percentage oracle this campaign landed earlier, and the
previous capture's own record predicted the next capture would fold it in. Peer
working-tree edits were present on the M303 tree at capture time; they add
comments and one verification predicate, and neither declares a grounding claim,
confirmed by grepping every uncommitted registry file for the declaration.

### Verification

Both directions the row demands, simulated through the real fold with the arrival
constructed from a real composed row so every derived count moves as a genuine
addition would.

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -v -k "ninety_first or
  stamping_campaign_is_underway or lost_translation or untranslated_leaves"

PASSED ...::test_a_ninety_first_revision_landing_unstamped_leaves_the_gate_green
PASSED ...::test_a_new_revision_stays_green_even_once_the_stamping_campaign_is_underway
PASSED ...::test_a_lost_translation_reds_the_gate_even_while_the_registry_grows
PASSED ...::test_new_casillas_adding_untranslated_leaves_leave_the_gate_green
4 passed in 42.11s
```

The green cases assert more than the pass. The arrival case asserts every
progress floor is byte-identical across the arrival, read through the real
capture path rather than a helper mirroring it, because asserting only "passed"
would hold equally well if the counters had been deleted. The mid-campaign case
asserts the reviewed fraction genuinely FALLS across the arrival before asserting
the gate stays green, which is what makes it a statement about the ruling rather
than about an unchanged tree.

The red case grows the required locale population by five in the SAME report that
deletes one authored leaf, so it proves the two are separated rather than proving
that any locale movement reds. Its paired case — the same growth without the
deletion — is what keeps it non-vacuous.

Reinstating the retired ceiling reproduces the reported failure exactly, on the
same arrival:

```
retired ceiling unreviewed_revisions = 90 at population 90
population after the arrival = 91
gate passed = False
  violation: unreviewed_revisions grew from 90 to 91
--- and the capture that would record the new state ---
refusing to record a baseline that weakens the ratchet:
  ceiling unreviewed_revisions would rise from 90 to 91, permitting more defects
```

That second half is the conflation the row names: the honest re-record is refused
until the operator asserts a deliberate weakening.

Disabling the progress comparison while leaving the counters recorded and
rendered — the "committed, printed, never consulted" failure — flips three:

```
FAILED ...::test_a_lost_operator_signoff_reds_the_operator_floor_the_review_floor_cannot_see
FAILED ...::test_the_operator_floor_gates_the_real_cli_at_the_committed_baseline
FAILED ...::test_a_lost_translation_reds_the_gate_even_while_the_registry_grows
3 failed in 55.44s
```

Every mutation was reverted and the module re-verified. Full module under the
DEFAULT selector, plus the integration-marked gate under its own marker, because
a bare path invocation deselects both its tests and reports a clean exit:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
84 passed in 71.28s (0:01:11)

uv run --no-sync pytest dev/tests/test_registry_conformance_gate.py -m integration -q
2 passed in 107.20s (0:01:47)
```

The shipped verb, and the new block on the screen:

```
python -m dev.registry.conformance audit --check -> exit=0
audit registry_validated=true passed=true ratchet_violations=0 vacuity_violations=0
      progress_violations=0 baseline_recorded_at=2026-07-28
progress counter=reviewed_revisions           current=0     required=0
progress counter=operator_reviewed_revisions  current=0     required=0
progress counter=revisions_with_engineered_by current=0     required=0
progress counter=translated_locale_labels     current=25767 required=25767
```

Style, lint and types:

```
uv run --no-sync ruff check ...           -> All checks passed!
uv run --no-sync ruff format --check ...  -> already formatted
uv run --no-sync ty check dev/registry/conformance/ -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. It was neither
started, restarted, reindexed nor probed. Grounding was whole-file reads of the
manager, the command and the test module, plus ripgrep sweeps for every consumer
of the four counters across both trees.

Three of the four governance progress floors stand at zero today, so they are
vacuous until the stamping campaign records its first claim. That is honest
rather than a defect — there is no progress to protect yet — but it means the
review-axis floors are proved only against seeded baselines, not against the
committed one. The locale floor is non-zero at 25767 and is exercised against the
real registry, which is why the translation cases carry the weight of the
committed-baseline proof.

One test assertion had to be rewritten mid-run: `reviewed_revisions` is a proper
suffix of `operator_reviewed_revisions`, so a substring exclusion phrased as "the
broad counter must not appear" matched the narrow counter's own sentence and
failed. It now asserts the whole set of moved counters, which cannot collide.

Peer campaigns held uncommitted work on the M303 registry tree and on two audit
baselines throughout. None was staged; the commit named its four files
explicitly. The M303 edits were read in full before the baseline capture, because
a capture folds whatever the working tree holds into everyone's committed floor.
