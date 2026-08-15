---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:088bc2588127e8b6ff5c7897769871b72458d8c1d7a608f68b898d23cdf0c59e'
step_id: 'S196'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh reconcile which fixture owns a test bucket directory, since the shared capsule seeding door and the isolated command-line runtime fixture both provision the same per-profile bucket path so the capsule's no-replace rename always refuses that destination as already existing, which reds the established reference pattern several suites were written against and is currently masked in some of them by an unrelated stale version literal

## Scope

- `src/cadrumo/tests/profile_capsule.py and src/cadrumo/tests/secure_sql.py and src/cadrumo/tests/bucket_layout.py`

## Description

- Reproduce the destination conflict at current HEAD before judging anything.
- Establish both doors' consumer sets and the ownership precedent two closed
  rows already set for this exact shape.
- Give the bucket root one creating authority in the test harness and prove the
  publication guarantee still refuses a genuine conflict.

## Outcome

The ownership ruling is that NEITHER test door owns the directory, because the
directory was never theirs to own. A bucket root is brought into existence
exactly once, by capsule publication's atomic no-replace rename, and the
storage layer refuses every other creator. The isolated runtime fixture was
simply a third creator, in the same class as the database engine closed by
`S49` and the dead adapter helper relocated by `S69` -- so this row is settled
the same way both of those were, by removing the second creator rather than by
inventing a third answer.

The mechanism was re-derived rather than inherited. The runtime fixture called
the test-support directory provisioner on the per-profile bucket path; the
seeding door then published a capsule for the same identity and its no-replace
rename found the destination occupied, which it must refuse because that rename
IS the atomicity primitive. Measured on a fail-fast run of the workflow resume
suite: `profile capsule destination already exists`, raised from the Windows
rename-by-handle path, at fixture setup.

The fix gives the runtime fixture a door onto the one creating authority
instead of a second creation path. A new test-support publication helper builds
the custody envelope, sentinel and record session from the same deterministic
identity-derived key the fixture's own session binds, and publishes a
revision-one record with no facts, deliberately incomplete -- exactly what the
production credential door leaves behind. The seeding door then finds a
committed capsule and takes its replacement branch through the same
compare-and-swap writer a real fact update uses. No tolerance branch was added
anywhere, and publication was not touched.

**The rejected alternative, and why.** Having the seeding door adopt an
existing prepared directory was rejected on two independent grounds. It would
either require publication to tolerate an occupied destination -- a custody
semantics change, not a test fix -- or require the seeding door to write
custody material into a directory publication never claimed, which
re-implements the single-writer publication path the architecture reserves.
It would also have the fixture keep constructing a state no production path can
reach: a bucket root with no capsule. That premise defect was the actual
defect; adopting it would have preserved it.

**The guarantee is intact and proven.** An out-of-repository probe, loaded as a
plugin off the path so no tracked file was mutated, shows both halves: the
fixture's bucket now carries committed custody alongside its database and blob
children and publishes without refusal, and when anything other than
publication occupies the destination first, publication still refuses with the
identical error. The no-replace rename was neither weakened nor bypassed.

## Notes

**A second premise defect surfaced in the fixture's own test module and was
fixed.** Its control bucket was identified by a free-form label rather than a
profile UUID. A bucket IS a published profile capsule, so a non-UUID bucket
identifier names a bucket no production path could create; the directory
provisioner accepted it only because it validated separators and emptiness
rather than identity. Two assertions there also had to stop being tallies:
a whole-table row count and a pinned namespace triple both silently assumed an
empty bucket, which is now false by construction, so they were re-expressed as
properties -- one row in the control namespace, and the routed namespaces on
top of a baseline captured at fixture entry rather than a literal set.

**The masking effect named in the row was measured, and the row's premise about
it needs correcting.** The row and the dispatch described the two named
reference modules as independently red for the destination conflict. They are
not. Both fail earlier, entirely on a stale profile schema-version literal in
their own test bodies, and never reach capsule publication at all: measured
before the change, eleven schema-version refusals and zero destination
conflicts across them. Their counts are therefore unchanged by this row and
they remain red for a cause owned elsewhere. Nobody should read the resume
suite's improvement as evidence about those two.

**Honest attribution of the resume suite's improvement.** Before: zero passed,
twenty-two setup errors, every one of them the destination conflict. After:
fifteen passed, seven failed, zero destination conflicts. The seven that remain
swapped cause rather than staying red for the same reason -- they now fail on
registry validation, which was previously unreachable because setup never
completed. That cause is ambient and was confirmed independent of this change:
a registry integrity module is red at HEAD on its own, naming missing corpus
files and unauthored export layouts from the in-flight registry sweep.

The fixture's own test module went from two failures to six passed, after the
second premise defect above was fixed. The user-profile package runs three
hundred and seventy-two passed against fourteen failed with zero destination
conflicts; every one of the fourteen was traced to a cause owned elsewhere --
registry validation, the changed seeding-door signature, retired profile
subcommands, the unavailable wizard creation path, and the cleared-path writer
policy -- and none to this change. That package takes twenty-four minutes
single-worker on this share and was run with parallelism disabled.

**Measurement was disrupted twice by concurrent work, and this is worth
carrying.** Mid-verification, every import of the custody chain began raising
because a class landed by the in-flight custody work carried no declared error
code entry. That is not a transient: it blocked the bare interpreter, the
plugin path and test collection alike, and it was resolved upstream by a peer
between two of these runs. The probe therefore neutralises that one unrelated
defect in process memory only, and reports whether the patch was needed, so a
later reader can tell which state the measurement was taken in.

**Working-tree edits were captured by peers' commits before this row could
present them, twice.** The fixture changes were swept into another session's
commit mid-verification, and the test-module changes landed later under a
commit naming a step identifier that is not this row's. Content is
byte-for-byte what this row authored and was re-verified green afterwards, but
neither change is legible in history under its own description or its own
identifier.

**Pre-existing gate failures deliberately not absorbed.** The import hygiene
gate is red with one hundred and one cross-package test-only private reaches
against sixty-nine documented. None of the thirty-two undocumented entries is
from this change -- the one import added here is intra-package, which the gate
does not count -- and the debt file lives outside this row's ownership.
