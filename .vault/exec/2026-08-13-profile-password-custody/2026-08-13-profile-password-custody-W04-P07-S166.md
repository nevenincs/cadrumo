---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e5b1c751ed904922d234a7068f298563debe9c56473e26acf25795a3ee6fe6d4'
step_id: 'S166'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh compose the full-corpus collectability proof into a lane that is actually run, since the harness that would have caught two test packages being uncollectable is real and mutation-tested but is enrolled only in a standalone recipe every other lane ignores and in a single separately-named continuous-integration job, so every routine local and integration run stayed green throughout the window those packages could not import, and a green lane structurally unable to see a collection error is what makes one read as infrastructure noise and get scrolled past

## Scope

- `justfile and .github/workflows/ci.yml`

## Description

- Verify the current enrolment state rather than re-derive it: the proof is a
  standalone recipe member and its own continuous-integration job, reached by
  no other lane.
- Establish which of the three candidate placements can survive, from the tree
  rather than from preference.
- Compose the harness verdict into the local recipe that already claims to
  answer whether the suite is clean, ordered ahead of both lanes.
- Leave the workflow unchanged, and record why the shipped pin makes that the
  correct action rather than an omission.
- Run the enrolled verdict and report what it found.

## Outcome

**Placement chosen: the local both-lanes recipe, ordered FIRST.** That recipe is
already documented as the one to reach for before claiming a suite is clean, and
the repository's own deselection hook points operators at it by name. It is
therefore the exact surface that was making the false claim: it composed the two
lane verdicts and nothing that could see a module which fails to IMPORT, so its
green meant "everything that happened to be collectable passed" and it had no
way to report what was not.

It runs ahead of both lanes for three independent reasons. An uncollectable
corpus invalidates the green the lanes produce, so the verdict that qualifies
them belongs before them. The task runner stops at the first failing line, so a
trailing position would never report at all on a tree whose lanes are already
red -- and two integration-marked tests are deliberately held failing in this
campaign, which makes that the tree's present state rather than a hypothetical.
And it costs a couple of minutes ahead of a run that already costs many, while
the fast inner loop is a different recipe entirely and is untouched.

It is a separate task-runner invocation, never folded into either lane's pytest
command line. The members spawn a real child pytest, so a lane that collected
one would nest a worker pool inside its own pool; the harness recipe owns the
outer-serial worker pinning and the per-member collect preflight, and delegating
to it keeps both intact.

**Rejected: a commit hook.** This repository has no commit-hook configuration at
all, so this would not be enrolment into an existing surface but the creation of
a new one, in order to put a multi-minute full-corpus collect in front of every
commit. That is the failure the row warns about: the first person it delays
disables it, and a gate everyone routes around is the same failure as a gate
nobody runs. It is also the one placement the concurrency problem below argues
against specifically, because a commit hook fires on a tree mid-edit by
construction.

**Rejected: making an existing continuous-integration job depend on it.** Not on
preference -- a shipped pin forbids it. That pin requires the harness job to
carry no dependency edge, to stay blocking, and requires the static and unit jobs
not to invoke the harness recipe; a companion assertion pins the workflow's job
set exactly, so adding a job would red it too. The shape is a deliberate,
gate-enforced decision: the harness reports independently so a load-sensitive
verdict cannot drag the deterministic ones down. The workflow already runs the
proof as a blocking job on every push, so the continuous-integration half of
this row was not the gap. **The workflow is therefore unchanged, and that is the
finding, not an omission.** The gap was local only.

**What collectability can and cannot see.** The proof establishes that every
discovered first-party test module IMPORTS. It does not execute a single test
body, so a construction that breaks inside a deferred function-local import
stays invisible to it exactly as it stays invisible to any collect-only pass and
to the per-module collectability gate. This enrolment therefore does NOT close
the deletion-without-consumer-sweep class in general: a helper building a retired
artefact inside a function-local import survives it untouched. The mechanism with
that capability is the whole-tree type gate, which a sibling step established is
red at rest and so cannot presently bite. What this enrolment closes is narrower
and real: a module whose top-level imports no longer resolve is now visible to a
routine local verdict instead of only to a job nobody reads locally.

**The enrolled verdict is RED at rest, on its first run, for exactly the class it
exists to surface.** Three modules under the agent-evaluation tooling tree cannot
be imported: all three import a user-profile repository symbol that has been
renamed in the application layer without its consumers being swept, and the
importer fails naming the old symbol. Reproduced deterministically in isolation,
so it is a genuine breakage rather than a transient. Both the renamed symbol's
package and the three consumers sit outside this step's ownership, so they are
reported and not edited. Their absence from every run is precisely the condition
the row describes: three modules contributing nothing while every lane reported
green.

**Concurrency, and why it does not argue against this placement.** The proof was
reported unreliable on this worktree because a peer session is writing the
registry data tree, which makes the loader raise its concurrent-write refusal
during collection. On this run that did not occur at all -- the failure list was
clean, deterministic and entirely real. The condition is not a property of the
harness: a tree being mutated underneath a collection breaks every lane the same
way, and the same run surfaced unrelated ambient failures from concurrent
temporary-directory removal. So no retry or settle-wait was added. A retry would
have to distinguish the transient loader refusal from a genuine intermittent
import failure, and it cannot: the collection reporter discards the error TEXT
and returns only module paths, so any retry built on today's return shape would
mask the second class to suppress the first. Surfacing that text belongs to the
collection reporter's own module, which is outside this step's ownership.

**Verified:** the harness recipe run end to end -- both collect preflights green,
then 4 passed and 1 failed, the failure being the full-corpus proof reporting the
three uncollectable modules above. The recipe parses and resolves to the three
delegated invocations in the intended order.

The shipped structural pins were re-run against the edited task-runner file: 119
passed, 4 failed, and the pin that governs this area -- the one asserting the
harness verdict is a standalone blocking job with no dependency edge and no
routine-job invocation -- is among the passing. The four failures are attributed
below and none is caused by this change; that is proved rather than asserted, by
showing the edited recipe declares no test lane at all, so the lane authority
every one of those pins reads is bit-identical before and after.

## Notes

- Attribution of the four failing structural pins, none of them this step's: one
  is a child-process collect that timed out at thirty seconds on a loaded shared
  machine and, on re-run, failed instead inside the session fixture with a
  missing temporary directory another concurrent session had removed -- ambient,
  and it also emitted access-denied warnings writing the cache directory. One
  reports an unwatched job in a runner-probe workflow this step never opened. One
  reports artifact storage in a workflow this step never opened. The last reports
  credential-store-marked tests under a persistence custody test directory that
  no lane names; that directory belongs to another agent's tree and the recipe
  listing those paths was not touched here.
- The proof that this change cannot have caused any of them: the lane authority
  derives lanes from recipes that carry a pytest invocation, and the edited
  recipe carries none -- it delegates to three others. Enumerating the declared
  lanes confirms the edited recipe contributes zero, so every exclusion,
  membership and reachability pin reads exactly what it read before.
- Reported, not fixed: three agent-evaluation test modules import a user-profile
  repository symbol under its former name; the application layer now exports it
  under a snapshot-oriented name. Both trees are held by other agents. This is a
  rename landed without its consumer sweep, and it is the concrete instance the
  enrolled proof exists to catch.
- The recipe keeps its existing name although it now composes three things. The
  name is cited from the deselection hook's operator message, which is outside
  this step's ownership, so renaming it here would leave that message pointing at
  a recipe that no longer exists.
- Two campaign tests are deliberately held failing and were neither fixed nor
  skipped. Both are integration-marked, so they red the third delegated
  invocation; the harness verdict runs first and is delivered regardless, which
  is part of why that ordering was chosen.
