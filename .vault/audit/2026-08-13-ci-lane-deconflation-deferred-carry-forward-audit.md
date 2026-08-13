---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7d3b1dc9504759b6f3d28216fc5698ed718873cc1d527ba1c47afe1a41717c37'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-adr]]"
---

# `ci-lane-deconflation` audit: `deferred carry-forward at 45 of 49`

## Scope

The four rows the ci-lane-deconflation plan still carries open at 45 of 49, each
re-measured against real runner evidence on 2026-08-13 rather than against the
state its row already recorded. The purpose is to record the deferred
carry-forward honestly: every one of the four closes only on evidence from a real
execution, none of that evidence can be manufactured locally, and two of the four
had been parked on a stated cause that the fresh measurement falsifies.

The re-measurement was possible because the condition every row was waiting on
changed. The single Linux runner's queue has drained. It reports online and not
busy, the eighteen-hour backlog is gone, and both runs the rows were parked on
have completed. What that produced is not four closures but two corrected causes
and confirmation that all four blockers are owned outside this plan.

## Findings

### docs-lane-ceiling-hypothesis-falsified | high | The 30-minute ceiling is not the docs blocker, and the row's standing conclusion is disproved by its own next observation.

The row had concluded, at length, that the documentation build does not fit the
30-minute job budget, that the ceiling is a genuine lane defect independent of
the runner swap, and that a cold build provably needs more than 30 minutes. Run
31679802188, a push-triggered Docs Check on 2026-08-13, falsifies that directly.
The job ran 07:55:29 to 08:15:59 UTC, twenty minutes and thirty seconds, and the
Build the documentation site step ran to a genuine completion well inside the
ceiling. It was not cancelled and not killed. The prior 30m17s datapoint was a
property of the freshly-provisioned WSL runner the row itself attributes to the
operator registration swap, not of the lane, and the inference drawn from it does
not survive a second observation.

Two facts the row banked are confirmed rather than disturbed. The build-before-read
ordering works: the build step executed instead of failing on an absent build
directory, so the thirteen original failures the row names stay closed. And the
concurrency setting is correct, since this run was superseded by nothing.

The consequence that matters is prospective. The row as written instructs the
next actor to raise the ceiling, and doing so would now be acting on a disproved
hypothesis, spending the change budget on a non-defect while the real blocker
stays open.

### docs-lane-blocked-on-host-fact-golden | high | The docs lane fails on a platform-conditional sequence golden owned by another campaign, with its fix uncommitted and in flight.

The same run failed for a specific, named, reproducible reason. The nitpicky
Sphinx build raised on a docs-sequences divergence: page workstation-setup,
sequence install-confirm, frame 3, the envelope diverging at post-mask paths
`result.preflight[7].facts.long_paths_enabled` and
`result.preflight[7].facts.platform_windows`. The recorded golden carries the
host facts of a Windows authoring machine; the Linux runner contradicts both, and
the host-conditional fact mask does not cover these two paths. The recipe exited
2 and the Documentation conformance step was skipped in consequence, so the lane
still produces no conformance verdict — but for a content reason rather than a
budget one.

This is another owner's live surface, not this plan's. The masking layer is under
active uncommitted work in the shared tree: `dev/docs/sequences/_golden_store.py`
carries a WIP change adding a JSON-escaped form to the path replacements, whose
own docstring refers to the host-conditional fact mask as a sibling layer, and
`docs/_sequences/workstation-setup/install-confirm.json` is modified alongside it.
The nearest landed commit on that surface masks host-measured facts. The fix is
therefore in flight rather than absent, and this plan must not touch those files.

CORRECTED ON THE SAME DAY, AFTER A FULL READ OF THE FAILING RUN'S LOG. The finding
above named the host-fact divergence as the blocker on the strength of the first
divergence the log reports. That is true but badly understated, and the correction
matters because it changes who must act and how large the work is. The build
actually raises on fifteen cli-sequence divergences spanning roughly
eighty-seven individual frame failures, of which the host-fact pair is two, on the
workstation-setup install-confirm frame 3 alone. The remainder are fourteen
duplicate capture-name parse errors for `evidence_id` across seven pages, fifteen
executed-argv divergences, two exit-code divergences, and a large body of stale
envelope goldens concentrated in observation values, operand values, result
summaries and calculation revision ids.

Two further facts sharpen the attribution. The host-measured-fact mask cannot
close this pair by construction: it matches fact keys by a `_bytes` suffix, and
the two diverging keys are booleans, so the narrow suffix rule is structurally
unable to reach them. And the masking commit that landed that rule was ALREADY an
ancestor of the failing run's own sha, so it was in effect and did not help.
Nothing on the docs-sequences surface has landed between that sha and HEAD, so the
tree is byte-identical there and the failure reproduces exactly.

The docs lane has NEVER once concluded success. Across its last hundred runs the
conclusions are seventy cancelled and thirty failure, none successful, so the
row's close criterion has no candidate run at all rather than merely lacking a
recent one.

### ci-full-blocked-before-its-build-branch | high | The serial-pass observation is unobtainable because the run dies in the style gate two and a half minutes in, on an 87-violation cross-package backlog.

Run 31674646030, the ci-full dispatch obtained specifically to watch the build
branch produce three wheels and three sdists, completed with conclusion failure.
It never reached the build branch. The run carries exactly one job, which ran
07:00:33 to 07:03:09 UTC, two minutes and thirty-six seconds, and died in
`just check-style` at the `check-relative-imports` recipe.

The blocker's identity has therefore changed again, and away from this plan a
second time. It was runner absence, then queue saturation; it is now a test-import
backlog. Re-run at HEAD rather than trusted from the log, the gate exits 1 with 87
violations, distributed across `src/cadrumo/application` at 62,
`src/cadrumo/domain` at 20, `src/cadrumo/adapters` at 3, and one each in
`src/cadrumo/tests` and `src/cadrumo/entrypoints`. A large share are registry
tests importing `resolve_available_bound_inputs_by_casilla_id` from
`cadrumo.application.modelo` by absolute path. That spread is a cross-package
backlog with many owners, it is not this plan's surface, and it stands between
ci-full and every observation downstream of the style gate — not only this row's.

THE SUSPECTED GATE OSCILLATION DOES NOT EXIST, and this is worth recording because
the fear of it is what would otherwise stall the remedy. The two gates were read
directly rather than inferred. The relative-imports gate governs SYNTAX: it bans an
absolute `cadrumo.*` import inside the package and never inspects the target. The
architecture boundary rule governs the TARGET: a cross-package import must resolve
to the owning package's public facade rather than a private module. A cross-package
RELATIVE import satisfies both at once, because relative syntax can perfectly well
name a facade. The house norm already demonstrates it at scale — deep multi-dot
relative imports are pervasive, including in the very directories holding the
violations — and the symbol at the centre of the largest cluster is already exported
on the `application.modelo` facade, so conversion is facade-preserving. There is no
third shape to invent and no reason to hide anything from either matcher.

THE CLUSTER HAS A SINGLE ROOT CAUSE, and it is a process gap rather than a design
one. The sixty-two-file group entered in one commit, a registry relocation retiring
the strict registry-domain bound-input resolver, which correctly swept every
consumer to the new path but wrote the new imports in absolute form and never re-ran
this gate. The atomic-relocation discipline was honoured for the move and skipped
for the gate, which is precisely how a clean refactor lands a tree-wide red.

OWNERSHIP IS CONFIRMED AND THE REMEDY IS ALREADY UNDER WAY, which retires the
routing recommendation this audit makes below. The backlog is being actively swept
by its owner, measured falling from 87 to 76 to 59 within a single session, with
uncommitted work in place promoting the shared fixture onto its package facade —
the stronger form the architecture rule mandates as a precondition of the consuming
change. This plan contributed one convention-identical file and deliberately stood
down from the rest rather than forking a second conversion convention against the
owner's, since two shapes for one import is exactly the fragmentation the rules
forbid. The precondition is therefore closing on its own and needs no intervention
from this plan.

### both-flip-rows-remain-correctly-parked | medium | The two continue-on-error flips stay parked, each on a release condition that is measured and unmet.

Neither flip row's condition has moved, and both remain right to refuse. The
dev-tooling row states its release condition as a backlog of zero; the most recent
sequential measurement recorded on the row is 83 failed with 48 errors, having
drifted from 70 and 68 at eight workers the previous day, so the backlog grew
rather than closed. Its populations have different owners by the row's own
accounting, and the 48 errors share a single cause in a Modelo 145 casilla label
untranslated in Spanish, which is a locale co-commit gap belonging to that owner.

The per-push conformance row needs two conditions and holds neither: the CLI
action-rendering refactor has not landed, and the measurement is 6 failed of 48
rather than zero, identical in count and split to the enrolment-day figure. Both
rows are functioning exactly as intended. Flipping either on anything short of its
stated condition is the specific failure the plan exists to prevent, and the plan
is explicit that a campaign may not narrow its own completion criterion.

## Recommendations

Do not raise `timeout-minutes` in the docs workflow. The measurement that would
have justified it is superseded, and the change would consume the row's remaining
budget on a defect that is not there. If a future cold build does exceed the
ceiling, that is a fresh observation to record, not a return to this one.

Leave the docs-sequences golden and its masking layer alone. The divergence is
owned by the campaign already holding uncommitted work in those two files; the
correct action is to let that land and take the next push-triggered Docs Check as
the observation, in keeping with the standing instruction on this row that no
dispatch be made to force one.

Route the relative-imports backlog to its owners as a cross-package concern rather
than absorbing it here. It is not a ci-lane-deconflation defect, it blocks far
more than this plan's one row, and its 87 violations span four top-level packages.
Its closure is the precondition for the serial-pass observation, so this plan's
row waits on it rather than working it.

Carry all four rows forward as deferred with these causes recorded, and treat the
plan as complete at 45 of 49 in delivered scope. Every remaining row is gated on
an external condition owned elsewhere, none can close on local evidence by the
plan's own verification criterion, and marking any of them complete would put
delivered-as-specified and blocked-on-another-owner under the same checkbox.
