---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:21e42b36896ad11eb4c1164128910c8c085e8284fb925a147cddc2fd8e3fe406'
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

ONE CAVEAT QUALIFIES THAT ADJUDICATION AND MUST TRAVEL WITH IT. "Mechanical
conversion is safe" holds for the SYNTAX question and not for every site. Where the
importing module sits in `domain` and the imported one in `application`, the import
is a hexagonal LAYERING reach regardless of how it is spelled, and rewriting it to
relative form makes the gate green while preserving the inversion untouched. That is
the same trap in a subtler guise: satisfying the syntax gate can conceal an
architecture defect rather than resolve it. Such a site needs the dependency
inverted or the symbol rehomed, never a spelling change. The conversion is therefore
mechanical only after the direction has been checked, per cluster rather than per
file.

In practice this caveat has already been overtaken by the sweep. At the time of
writing the residue is six violations with ZERO domain-to-application sites among
them: the twenty-strong domain cluster is closed. All six sit in a single
application-package test module and are intra-package, five of them reaching that
package's own private modules plus one to `core`, so no layering dimension arises
and relative conversion is unambiguously correct there.

A SECOND OBSERVATION MATTERS MORE FOR WHETHER THE GATE STAYS GREEN. That single
remaining file landed in a fresh commit during this very session, which means the
backlog is being re-fed while it is being swept. A sweep alone therefore cannot
close this permanently: the gate goes green and the next commit written with
absolute imports reopens it. Durable closure needs the violation caught at write
time — the same lesson the root cause already taught, since the 62-file cluster
entered through a relocation that never re-ran the gate.

THAT WRITE-TIME REMEDY IS RETRACTED BY OPERATOR RULING, and the retraction matters
more than the observation it corrects, because acting on the paragraph above would
do active harm. The commit-time enforcement stage does not merely happen to be
missing in this tree: it is deliberately uninstalled and stays that way until the
project settles. A commit-stage autofixing hook destroys work in a shared worktree
where many agents hold uncommitted changes concurrently, which is the same hazard
that governs autofixers and destructive git verbs here. Restoring it to close a
lint backlog would trade a cosmetic red for silent, unattributable loss of peers'
work. The measurement behind the paragraph above stands — no commit-stage hook is
installed, the hooks path resolves to a directory holding only post-stage hooks, and
every gate declared in the hook configuration is therefore inert — but the
conclusion drawn from it does not. Absence here is a decision, not a defect.

DURABLE CLOSURE IS THEREFORE AUTHOR DISCIPLINE PLUS A GREEN FULL-TREE RUN, not an
enforcement mechanism. A relocation re-runs the gate before committing. That is
precisely the discipline whose omission produced the 62-file cluster, so the root
cause and the remedy meet in the same place, and the remedy is a habit rather than a
hook.

A CONSEQUENCE WORTH INHERITING: zero is not a stable state for this gate in this
tree, and cannot be made one. A reader who finds the count non-zero after it was
reported green should read that as the expected behaviour of an unenforced gate
under concurrent authorship, never as evidence that someone failed to finish the
sweep. This does not soften any row's condition — the condition remains the
condition — it explains why the condition oscillates.

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

BOTH ROWS RE-MEASURED THE SAME DAY, AND THE DEV-TOOLING BACKLOG HAS TURNED. The
dev-tooling lane now stands at 76 failures and 6 errors against the 83 and 48 the
row records, so failures fell by seven and errors by forty-two, total red dropping
from 131 to 82 while passes rose from 1694 to 1832. The direction is finally
favourable rather than drifting. The forty-two closed errors are fully attributed:
they were never a missing translation but six Modelo 145 casillas added without any
locale key at all, by a commit that deliberately excluded the catalogues as under
active edit, and a scaffold commit twenty-one minutes later took the Spanish
catalogue from fifty to fifty-six real labels. All four catalogues now carry
fifty-six keys and that population is gone. The residue is 76 failures over
twenty-six modules and at least eight distinct owners, plus six errors that are a
single environmental cause, the concurrent-registry-write fingerprint race. The
release condition is zero, so the row stays parked, but its figure must be restated
as 76 and 6.

The per-push row's second half is now MEASURED rather than merely unconfirmed. The
CLI action-rendering refactor is the cli-action-envelope-hardening campaign, and it
stands at 76 of 120 steps with 44 open and the whole of its sixth wave untouched, so
"in flight" is now a number rather than an impression. Its own measurement
re-confirms at six failed of forty-eight, the identical six tests in the identical
two-and-four split, and the diagnostic output names the refactor's own modules in
roughly forty-five stale-disposition lines. Two of the six fail for an unrelated
reason worth separating: a shared profile-creation fixture now refuses because the
setup flow has grown five further required answers, which is the profile setup-flow
campaign's moving surface and not this lane's.

A SESSION-KILLING DEFECT WAS FOUND WHILE MEASURING, and it belongs to dev/audit
rather than to this plan. The security scan invokes a subprocess with a timeout and
handles the expiry, but the standard library's own expiry path kills the child and
then drains its pipes without a bound. On this platform the kill reaches only the
launcher shim while the real grandchild keeps the inherited pipe open, so the drain
never returns. The test that hangs is the very one asserting that the timeout path
is bounded. It passes in isolation in forty seconds and wedges only under load,
which is why a whole-lane sequential measurement is unreliable on a contended host
and had to be taken in two segments. This is a genuine defect, not a flake, and it
should be routed to dev/audit's owner.

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
