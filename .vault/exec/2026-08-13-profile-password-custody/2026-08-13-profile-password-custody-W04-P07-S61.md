---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:c3a18a16999adc3fae5dd2921322ffbb03a79a67968bff2ae2d9efecf501c664'
step_id: 'S61'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh bring the integration test lane under a standing watch

## Scope

- `pyproject.toml and src/cadrumo/entrypoints/cli/tests/`

## Description

- Census the lane honestly before proposing any mechanism.
- Establish whether a watch is the right instrument at all.
- Attribute the failure mass by cause rather than by count.

## Outcome

**Ruling: do NOT build or enable a watch, and the reason is upstream of the
mechanism question.** A standing watch already exists and is stronger than this
row specified -- it asks the CI-invoked question rather than the merely-declared
one, accepts only a precondition marker as an excuse, keeps no baseline or
allowlist, and recomputes each run. Building a second beside it would be the
duplication this campaign exists to remove.

And the lane cannot presently complete a sequential run at all, which is decisive:
**a watch cannot be placed on a lane that cannot finish.** Four distinct blockers,
each established separately -- a plain sequential run aborts at collection on two
registry modules so nothing executes; continuing past collection errors wedges on
a single test stuck in an asynchronous loop, and on this platform the
thread-based timeout takes the whole session rather than the test; one parallel
distribution mode dies with an internal scheduler error that suppresses the
summary entirely; and plain parallel loses a worker. Only one distribution mode
with per-area batching completed cleanly, and the author explicitly refused to
let its numbers be quoted as sequential-authoritative.

**The census is the deliverable, and it reframes the problem.** Roughly twelve
hundred and sixty-seven failures against twenty-nine hundred passes, with eighty
percent of all failures concentrated in the entry-point surfaces. Attribution by
share of classified error lines: about thirty-six percent the custody and
profile-record cutover, twenty percent the registry sweep, fifteen percent the
schema build for the unresolved command subtrees. So roughly seventy-one percent
is three in-flight campaigns rather than an evenly spread rot, and the genuinely
unrelated residual is around five percent.

**The single largest item is not a regression at all.** Two hundred and
ninety-four occurrences -- about twenty-three percent of the entire lane's
failures -- are one assertion: tests asserting a wizard profile-creation
capability that this campaign deliberately retired in favour of registration with
credentials. Stale tests, not broken code. That materially changes what the
headline percentage means, and it is this campaign's own debt rather than
someone else's.

## Notes

The strengthening of the zero-execution hook was declined on the condition set
for it, with three independent reasons rather than a preference. It is not a
one-line change: the hook runs from terminal summary, which cannot set exit
status through the public interface, so failing there needs new session-finish
wiring. Its zero-execution branch is only reachable in states where the framework
already exits with a no-tests-collected status, verified on both selection paths.
And it does nothing for the mixed run, which is the actual trap -- there some
tests execute, so the branch never fires. It would add wiring to close a path
already closed while leaving the real defect untouched.

The author refused to present the completed run as sequential-authoritative even
though it was the only complete measurement available, and reported the same
figure reproducing across two invocations as evidence of stability rather than of
authority. Given how many counts in this campaign have turned out to be artefacts
of a pipe, a marker or a dead worker, that restraint is worth more than the
number.

Two consequences are carried as their own rows: the two hundred and ninety-four
stale creation tests, sequenced behind the ruling on whether scripted profile
creation is permitted so the rewrite is not done twice; and the wedging test,
because one hanging test denying the entire repository a sequential run is
upstream of every measurement anyone tries to take of that lane.
