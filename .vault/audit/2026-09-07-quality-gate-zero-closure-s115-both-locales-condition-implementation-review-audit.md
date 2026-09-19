---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d9b34fc7d2eee8f34e16890df79024f781016b15eeebf1dee74368955a9c06e9'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
---
# quality-gate-zero-closure audit: S115 both-locales condition implementation review

## Scope

Reviewed W08.P25.S115 against the accepted locale-axis decision and the owning
plan. The review covered the locale gate and fixture, the eight repaired live
sites as reflected by the before/after detector evidence and focused behavioural
runs, and the S115 execution record. The deciding question was whether the
parameterized test executes the affected assertions under two rendered locales or
only invokes the static detector twice. No production, test, workflow, or execution
record was changed.

Current implementation evidence is otherwise sound: the complete pre-repair
catalogue sweep failed first with seven English-only sites under the Spanish axis
and one Spanish-only site under the English axis; no shipped source was seeded.
Repairs pin real CLI invocations or rename a non-CLI variable so it is outside the
detector's output claim. Eleven affected behavioural modules pass, the repaired
locale gate passes 53 tests, focused Ruff and formatting checks pass, and no mock or
monkeypatch is present.

## Findings

### static-sweep-is-not-the-required-runtime-axis | high | the affected assertions are never executed under both locales

test_no_locale_bound_absence_survives_the_two_locale_axis parameterizes
ambient_locale over es and en, but its body only parses source and calls
scan_locale_bound_assertions. It does not collect the detector hit locators as
pytest node IDs, invoke any affected test, or vary the rendering locale seen by
those assertions. The initial red result proves the static detector recognizes
locale-bound source; it does not prove that each reported assertion passes under
the ambient locale and a second locale.

The distinction is load-bearing in the accepted decision. It explicitly rejects
merely flipping ambient detector interpretation because that mirrors vacuity and
cannot reach a test pinned at its call site. The current repairs then pin the real
invocations and remove them from the detector hit set, so the green static sweep
makes the required runtime population disappear without ever exercising its
members on the second locale. S115 therefore does not deliver the condition it was
written to deliver.

### execution-record-preclaims-closure | high | the record contradicts current evidence and attributes S116 work to S115

The S115 execution record says the initial demonstration produced five findings in
each direction and that all 50 tests passed after S116. Current authoritative
evidence is seven English-only findings under Spanish, one Spanish-only finding
under English, and 53 passing gate tests. S116 is still the separate repair Step,
yet its effects are used to claim S115 closure. The record also lists no runtime
invocation of the eight affected assertions under two locales. This stale and
cross-Step evidence cannot authorize a pass/fail claim for S115.

## Recommendations

For static-sweep-is-not-the-required-runtime-axis, retain the detector as the
selector, map each pre-repair hit to its actual pytest test node, and parameterize
execution of that bounded set so each affected assertion runs against ambient and
second-locale rendering. Explicit call-site pins must be varied by the axis rather
than made unreachable by an ambient environment change. Preserve evidence that
this runtime mechanism failed before repair, then show the same runtime selection
passing after repair. Do not create a lane, seed shipped source, or use a mock,
monkeypatch, exclusion, or threshold.

For execution-record-preclaims-closure, replace the stale counts with the observed
seven-plus-one demonstration, separate S115 mechanism evidence from S116 repairs,
and record the exact bounded runtime pytest invocations and outcomes. Do not close
S115 on the static detector sweep or on behavioural tests run in only their pinned
locale.

S115 is not approved. Two high findings remain; no critical finding was found.
**2026-09-07 pytester runtime re-review - static sweep finding resolved.**
The current bytes use pytester.runpytest_subprocess for both the live selected nodes
and the isolated positive control. The positive control now derives its node ID
through the same path-and-line resolver used by the live axis. Its temporary
non-collected source executes under both declared locales with plugin autoload
disabled, producing the required Spanish pass and English AssertionError. The
focused runtime-axis and class-method controls both pass.

Independent probing also resolved a synthetic assertion line to its containing
top-level function and class method and confirmed that a line outside a test node
raises ValueError. The live mechanism deduplicates resolved node IDs, executes
every node under en and es before accepting a non-empty detector hit set, and
retains collection or test failure as a red runtime outcome. Environment mutations
are restored in finally paths. No mock or monkeypatch, shipped collected seed, or
new lane is present.

The authoritative full gate result is 54 passed in 67.14 seconds, and the eleven
repaired behavioural modules pass. The implementation therefore satisfies the
runtime both-locales requirement and closes static-sweep-is-not-the-required-
runtime-axis. No high or critical implementation finding remains.

Execution-record-preclaims-closure remains the only high finding until the
acknowledged stale S115 record is rewritten with the seven-plus-one initial
failure, 54-test current result, pytester runtime mechanism, and separate S116
ownership. No critical finding remains.
**2026-09-07 repository-marker re-review - runtime repair works but is not regression-protected.**
The current implementation adds `-m ""` when executing real repository nodes and
keeps plugin autoload disabled only for the isolated fixture. An independent probe
against the integration-marked
`test_auth_families_have_one_canonical_registered_operation_each` reproduced the
failure mode: without the override pytest collected one test but deselected it under
the repository default marker expression and exited 1; with `-m ""` the same exact
node executed and passed. The current bytes therefore close marker deselection in
the live helper branch.

### repository-marker-override-has-no-positive-control | high | removing the marker override leaves the committed gate green

The planted runtime-axis control always calls `_run_node_under_locale` with
`isolated_config=True`, so it never exercises the real-repository argument branch
that owns `-m ""`. The class-method control stops at node-ID resolution. After the
eight live findings were repaired, the complete real-tree sweep has an empty hit
set and likewise never calls the helper against a repository node. Consequently,
removing `-m ""` recreates the exact marker-deselection defect while all 55 current
tests can still pass. The implementation is presently correct, but the gate still
cannot fail for this adjudicated regression.

For repository-marker-override-has-no-positive-control, add a bounded positive
control that resolves and executes a real repository node whose marker is excluded
by the default expression through the non-isolated helper branch, and assert that
it actually ran rather than accepting collection or deselection. The control must
remain mock- and monkeypatch-free and must not add a lane, exclusion, threshold,
or shipped seed.

S115 is not approved. The marker implementation works, but
repository-marker-override-has-no-positive-control and the previously recorded
stale execution-record finding remain high. No critical finding was found.
**2026-09-07 repository-marker and mutation-control resolution re-review.**
The new `test_runtime_axis_overrides_the_repository_default_marker` drives the
non-isolated `_run_node_under_locale` branch against the real integration-marked
`test_auth_families_have_one_canonical_registered_operation_each` node. It requires
a zero return code, the explicit `1 passed` execution signal, and absence of a
`deselected` signal. Independent focused execution passed in 7.40 seconds. This is
the positive control requested by repository-marker-override-has-no-positive-
control and closes that finding: removing the `-m ""` override can no longer leave
the committed gate green.

The bounded mutmut report is also consistent with an honest detector claim: 475
mutants were selected, 437 were killed initially, the 14 classified behavioural
survivors were all killed by targeted controls, and the remaining 24 are the
classified inert/equivalent cohort rather than reported as killed. The configured
mutation source includes `locale_bound_assertions.py`; the selected test set
includes its dedicated gate, and the copied roots preserve the real-tree sweep.
No mock or monkeypatch appears in the gate or its fixture.

No high or critical implementation finding remains. S115 nevertheless remains
unapproved solely because execution-record-preclaims-closure is still high: its
stale and cross-Step evidence must be corrected before the Step can be closed.
**2026-09-07 final execution-record re-review - approved.**
The rewritten S115 record now matches the reviewed evidence. It records the actual
seven English-only findings under the Spanish axis and one Spanish-only finding
under the English axis; the isolated runtime fixture's Spanish pass and English
AssertionError; the real integration-node marker control and its explicit
execution signal; the current 63-test result; and the exact 475 selected, 451
behavioral kills, and 24 classified inert mutation disposition without laundering
the inert cohort into a kill percentage.

The record also keeps the Step boundary intact: S115 owns the detector-selected
both-locales runtime mechanism and its fail-first proof, while S116 separately owns
the shipped assertion repairs that empty the live hit set. Its Scope, Changes,
Failure demonstration, Verification, Mutation proof, and Boundary sections no
longer preclaim S116 work or rely on stale counts. This closes execution-record-
preclaims-closure.

S115 is approved. All recorded high findings are resolved, and no high or critical
finding remains.

**2026-09-07 final runtime-axis and record re-review.** The committed non-isolated positive control now executes the integration-marked repository node through the same helper used for detector hits, requires `1 passed`, and rejects any `deselected` result. Removing the explicit empty marker expression therefore makes the gate fail. This closes `repository-marker-override-has-no-positive-control`.

The S115 execution record now states the seven-plus-one pre-repair hit set, keeps S116 repair ownership separate, names the isolated and real-repository runtime mechanisms, and records the final exact-byte mutation evidence. A fresh focused snapshot passed 63 tests. Its bounded run selected 475 mutants, killed 452, and left 23 individually disposed semantic equivalents; no behavior-changing survivor remains. The snapshot hashes match the current detector, test, and both fixture files, and its external scratch was removed. This closes `execution-record-preclaims-closure`.

S115 is approved. All recorded high findings are closed; no high or critical finding remains.
