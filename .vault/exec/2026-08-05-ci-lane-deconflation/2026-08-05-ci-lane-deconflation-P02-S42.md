---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:957b4bc99d5012e1947e2d57c8e11ac5fb16cd26cc26bbe841f914d9f9991e91'
step_id: 'S42'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Decide where the five drift census gates belong, because the instruments this fleet built to detect drift are themselves in the non-blocking tier and a census that cannot fail a build is a report rather than a gate. The five are the hex-64 redeclaration census, the identifier-noun census, the write-site census, the CLI-action census with its dispositions companion, and the variable-envelope generation gate under the registry dev tests. All sit outside testpaths, so no default invocation reaches them, and their only lanes are a tooling recipe no workflow invokes plus a continue-on-error step in a dispatch-only workflow. Choose between enrolling their directories in testpaths, which makes every local run pay for them, and adding an invoked blocking recipe that names them explicitly, and record which was chosen and why rather than leaving the reader to infer it from the configuration. Note when deciding that these gates are AST and filesystem sweeps over the source tree rather than behavioural tests, so their cost profile is collection-heavy and their failure mode is a census that silently measures nothing

## Scope

- `pyproject.toml and justfile and dev/tests and dev/registry/tests`

## Description

- Locate the five and confirm their present reachability rather than accepting
  the row's description of it.
- Measure their cost, which the row names as the deciding input against
  testpaths enrolment.
- Read the markers on all six modules, because a path enrolment that the
  marker expression then deselects is enrolment that runs nothing.
- Establish whether testpaths enrolment would in fact reach a CI lane, which
  the row assumed it would not.
- Record the decision and its grounds.

## Outcome

DECISION: an invoked blocking recipe that names them, specifically by
extending `test-dev-ci`. NOT testpaths enrolment.

Two of the row's premises did not survive checking and the decision rests on
what replaced them.

The row says their only lanes are a tooling recipe no workflow invokes plus a
continue-on-error step in a dispatch-only workflow. The recipe IS invoked --
`just test-dev-tooling` runs at ci-full line 254 -- and that step is the
continue-on-error one. Separately, four of the five sit under `dev/tests`,
which the ci-full step at line 115 reaches WITHOUT continue-on-error, so those
four already have a blocking home. What none of them has is a home in an
AUTOMATICALLY TRIGGERED workflow, because ci-full is dispatch-only. That is
the real gap and it is narrower and more precise than the row states.

The row also assumed testpaths enrolment buys local cost without CI coverage.
It does not. The `test-unit` recipe passes NO paths, so it inherits testpaths,
and ci.yml runs `just test-unit` in the blocking per-push unit job. All six
modules are `pytest.mark.unit`, so the default marker expression selects them.
Testpaths enrolment would therefore genuinely reach the per-push blocking
lane, which makes this a real choice between two working options rather than
one working option and one that only looks like it works.

Cost measured at 4 minutes 24 seconds for the five at `-n0`, which under
`--dist=loadfile` across six modules bounds their parallel cost at roughly the
slowest single module. The per-push unit job carries a 40-minute ceiling, so
either option fits. Cost is therefore NOT the deciding factor, which is worth
saying plainly because the row expected it would be.

The deciding factor is that this repository has already ruled on where dev
lanes are declared, and testpaths enrolment would contradict that ruling.
ci.yml's own step comment states it: every `dev/` lane is declared in the
justfile and nowhere else, because the step once restated four directories
inline while the justfile declared eleven more, the two sets overlapped by
nothing, and no single place answered what runs under `dev/`. Putting dev-tree
selection into pyproject's testpaths creates a second such place, and it is
the least visible of the available places -- a developer asking why a census
sweep runs on their bare `pytest` invocation would have no reason to look
there.

Testpaths is also the blunter instrument in a way that matters here. It
enrolls DIRECTORIES: `dev/tests` holds 16 modules and `dev/registry/tests`
holds 16, of which six are the census gates. The named-recipe form can carry
the same directories when that is right, but it does so where a reader
already looks for the answer.

## Notes

The implementing edit is deliberately NOT made in this row, and the reason is
a constraint rather than a preference. A 142-file unresolved merge is open in
this worktree, and the census gates read the source tree that the merge has
left holding conflict markers. Their current red is merge damage, not a
backlog: `src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py` carries
markers at lines 1211-1215 and does not parse, which is the direct cause of
the exception-override census raising. That file parses clean at HEAD.

That matters for this row specifically because the exact path list to add to
`test-dev-ci` needs one clean measurement of `dev/registry/tests`, which is
currently unmeasurable for the same reason. The decision the row asks for does
not depend on it; the edit does. Recording the decision now and the edit
against a clean tree is the honest split, and it is stated here rather than
left for a reader to discover.

The near-miss is worth recording because it nearly became this campaign's
sixth wider-or-blinder remedy. The first measurement showed 12 failures across
the five, and the natural reading was an accumulated backlog that had to be
closed before any blocking enrolment -- exactly the sequencing S43 records for
the format sweep. Intersecting a second run is what surfaced the parse error
in the message text and turned a supposed backlog into one peer's conflict
markers. The plan's own rule against triaging a lane from a single run earned
its place twice in one campaign.
