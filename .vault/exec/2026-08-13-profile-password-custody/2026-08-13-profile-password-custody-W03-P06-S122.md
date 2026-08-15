---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d444babb4a696ef9ad0dc4a00f9d40447d2f7d08bcefc3500c671a4d1597f0ae'
step_id: 'S122'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-found the setup-incomplete surface tests on the current custody authority, since they manufacture a bucket without a committed capsule by writing the retired plaintext manifest and the system now refuses that artefact by name, noting the collision fixture built for the label-ambiguity module does not fit because this one wants an uncommitted bucket rather than two colliding labels

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_profile_setup_incomplete_surface.py`

## Description

- Established that the scoped path has never existed. The module has lived in
  the CLI package's own test directory since it was first added, and never in
  the config package's. This matters beyond pedantry: the real location is a
  directory this row's dispatch fenced off as another owner's, so the row as
  written cannot be executed without a cross-owner ruling.
- Read the module as it stands today against the version first committed, and
  found the row's premise already half-overtaken by a peer sweep, in a
  direction that LOST coverage rather than restoring it.
- Confirmed the retired plaintext member is named retired by the custody
  capsule-discovery module, consistent with the closed rows that settled its
  retirement, and did not re-open that question.
- Located how a genuinely uncommitted bucket is produced today, from
  production symbols rather than staged artefacts.
- Read the live classifier behind the surface and established which half of
  the original surface still exists.
- Wrote a standalone proof outside the repository that registers a real
  profile, drives the real CLI, and checks the surface; ran it and captured
  the output.
- Proved the candidate coverage bites, by breaking the production classifier
  at runtime from outside the repository and confirming the assertion goes
  red, then restoring it.
- Wrote the candidate module in landable form and left it in the session
  scratchpad pending the ownership ruling.

## Outcome

**The re-founding mechanism is established and proven. The code was NOT
landed, because its file is in a directory this row's dispatch assigned to
another owner. Everything short of the edit is delivered.**

### The re-founding mechanism

A profile is born INCOMPLETE at registration and reaches COMPLETE only at the
setup-commit compare-and-swap. So an uncommitted bucket is not something to
manufacture at all: it is what registration already produces, and completing
setup is the separate second act. The shared CLI registration door in the test
support package takes a flag for exactly this, and its own docstring names the
case — pass the flag for a test whose subject is the incomplete state.

That is the whole mechanism. Nothing is staged on disk, no retired member is
written, no manifest is reconstructed, and the schema that once parsed it stays
retired and unread. The stimulus is the production path, not an imitation of
one.

### Why the collision fixture did not fit, confirmed rather than assumed

The row warned it would not, and inspection agrees for the reason the row
gave and one it did not. The label-ambiguity fixture builds TWO buckets
carrying colliding labels; this surface needs ONE bucket that was never
committed, and label collision is orthogonal to setup state. Borrowing it
would have produced a bucket that was complete AND ambiguous, which exercises
neither thing.

The reason the row did not give is the more useful one. Only ONE profile is
needed here, and that is what keeps this row clear of the live handover defect
the dispatch warned about: registering a SECOND profile in one process
currently fails inside interrupted-handover recovery. A fixture built the
obvious way — a workable profile beside an uncommitted one, which is how the
ORIGINAL module was written — walks straight into it. The single-profile shape
is not merely sufficient, it is the shape that can run today.

### What the peer sweep did, and the coverage that is currently missing

The module was rewritten by a peer's sweep commit before this row began, and
the rewrite accepted the drift instead of correcting it. The original module
covered the setup-incomplete surface in three tests: the listing naming the
status per row with an info advisory, an anti-tautology all-complete case, and
the calendar naming a mid-setup profile without counting it. The rewrite
re-pointed the assertions at the retired-custody refusal the staged member now
triggers, kept the filename, and dropped every setup-incomplete assertion
including the anti-tautology one.

So the surface this module is named for currently has ZERO coverage, and the
filename says otherwise. That is worse than an obviously broken test, because
it reads as covered. The two refusal tests the peer wrote do cover a real live
guard and are worth keeping; they simply belong under a name that says what
they test.

### A capability finding this row surfaced and does not own

Driving the real CLI against a genuinely uncommitted profile showed the two
halves of the surface are no longer in the same state.

The calendar half is ALIVE and correct. It names the profile on its own marker
line and reports zero calendar-bearing profiles, so a mid-setup profile is
neither hidden nor counted.

The listing half is GONE. The listing payload for that profile carries a name,
a bucket id and an active flag, and nothing else — no setup status, and no
advisory. The advisory's catalogue entry still exists and has no producer
anywhere in the source tree. So a mid-setup profile is now rendered in the
listing indistinguishably from a workable one, which is precisely the
condition the original test was written to prevent.

This is reported, not fixed. Whether that removal was a decision or another
capability lost without one is a question for whoever owns the listing
surface; this row can only record that the loss is real, that the orphaned
catalogue entry is the evidence it was once deliberate, and that no test would
now notice.

Consequently a re-founded module can honestly cover the calendar half only.
Writing a listing assertion today would mean asserting the reduced payload,
which would freeze the loss into a contract.

### Verification and its honest limits

The candidate coverage was proven outside the repository, driving the real CLI
against a real registered profile with no test doubles.

The uncommitted case PASSES: the profile is named on its own line, the label
is the one registered, and the calendar-bearing count is zero.

It BITES. Breaking the production classifier at runtime so a mid-setup profile
is dropped rather than named — the exact defect the coverage exists to catch —
turns the assertion red. Restoring the classifier turns it green again. The
break was applied from outside the repository, so no tracked file was mutated
and no peer sweep could have captured it.

The anti-tautology companion case, a committed profile that should be counted
and raise no incomplete line, is UNPROVEN and honestly so. It is the only case
that builds an actual calendar, so it loads the registry authority, and the
concurrent authority-grade sweep has that load refusing tree-wide right now
over unrelated export-layout and authority-grade complaints against several
modelo revisions. Five retries across a wide window all refused for that same
cause. The case is written and is expected to pass once the sweep settles; it
is recorded as unproven rather than quietly dropped, because an anti-tautology
case that was never observed to pass is not evidence of anything.

One incidental finding shapes the assertion and is worth recording: the bucket
id is REDACTED on this surface. An assertion embedding the registered id fails
against the redaction token. The candidate therefore matches the row by its
marker and the label it names. The original module's id-bearing expectations
could not have been carried over unchanged either.

## Notes

No source file was modified by this row, and that is the row's main
shortfall rather than a clean outcome. The candidate module is written,
proven, and sitting in the session scratchpad; landing it needs a ruling that
either grants this row the fenced file or hands the row to that directory's
owner. The ruling was requested at the start of the row, with the conflict and
three options set out, and had not arrived when the row was written up.

This row does not re-open the retired plaintext member's status, consistent
with the closed rows that settled it. Nothing in the candidate writes one, and
the retired-member anchor in the custody capsule-discovery module remains the
naming authority.

Two attempts to run the candidate under pytest from the scratchpad failed on
collection for environment reasons rather than test reasons: the repository's
session-scoped temporary directories were being torn down underneath the run
by concurrent peer sessions. The standalone proof script avoids the shared
session lifecycle entirely and is what the verification above rests on.

No commit was made, no plan checkbox was set, and every capture lives under
the session scratchpad rather than the repository.
