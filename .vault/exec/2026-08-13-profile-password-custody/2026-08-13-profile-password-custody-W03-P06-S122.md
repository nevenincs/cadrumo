---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f3d865342635570e51d719f314aa100400a3b7e38d2fd7db260440f9a8210384'
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
- Obtained the ownership ruling the row needed, the fence having been lifted
  once the holding agent's row closed, and landed the work.
- Split the module in two, so each subject sits under a name that describes
  it, and gave the shared registration helper the incomplete-state passthrough
  its underlying door already supported.
- Re-ran the bite-proof against the LANDED test rather than the scratchpad
  candidate, breaking the classifier through a plugin loaded from outside the
  repository.

## Outcome

**The re-founding mechanism is established, proven, and LANDED. One case is
green and bite-proven; its anti-tautology companion is blocked by an ambient
registry refusal and is recorded unproven rather than claimed.**

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

### A coverage deletion disguised as a re-founding — the row's real finding

This is recorded as a result in its own right, not as background to the
re-founding, because it is a distinct defect with a distinct lesson.

Sweep commit `518118f8be`, "registry: continue authority-grade sweep (round
21)", re-founded this module on the WRONG SUBJECT and kept the filename. The
original covered the setup-incomplete CLI surface in three tests: the listing
naming the status token per row with an info advisory, an anti-tautology
all-active case, and the calendar naming a mid-setup profile without counting
it. The rewrite re-pointed the assertions at the retired-custody refusal that
the staged member now triggers, and dropped every setup-incomplete assertion
including the anti-tautology one. Its whole diff was three lines: two
assertions removed, one substituted.

The net effect is that a surface still LIVE in production — the calendar's
classifier and its marker line, with a matching advisory entry in the locale
catalogues — had ZERO coverage, while the filename went on asserting it was
covered.

A file whose NAME claims coverage it no longer provides is worse than an
absent file, because nobody goes looking for it. An absent module is a gap
someone eventually notices; a mis-aimed one is a gap that reads as closed.
This is the same failure the campaign's standing audit describes as
delivered-narrower wearing the same checkbox as delivered-as-specified, and
it reached the tree through a sweep whose stated subject was something else
entirely.

The two refusal tests the sweep wrote do cover a real live guard and are
KEPT. They were never the problem; their name was. They now live in a module
named for the refusal they assert, so neither subject is hidden behind the
other's name.

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

### What landed

The module is split so each subject carries its own name. The
setup-incomplete module now covers the calendar classifier on a genuinely
uncommitted bucket; the retired-custody refusal tests move verbatim into a
module named for the refusal they assert. Each module's docstring records why
the two were separated, so the next reader meets the reason rather than
re-deriving it.

The shared CLI registration helper gained an incomplete-state passthrough. The
door beneath it already supported the state; only the helper withheld it, so
this exposes an existing capability rather than adding one.

### Verification and its honest limits

Real CLI, real registered profile, no test doubles anywhere.

Three of the four tests PASS: both refusal tests in their new home, and the
uncommitted case, which finds exactly one marker row, ending in the label
registered, alongside a calendar-bearing count of zero.

The uncommitted case BITES, proven against the LANDED test rather than a
candidate. A plugin loaded from outside the repository breaks the production
classifier so a mid-setup profile is dropped rather than named — the exact
defect this coverage exists to catch — and the test goes red; without the
plugin it is green. Nothing under source control was mutated to prove it, so
no peer sweep could have captured the break.

The anti-tautology companion — a committed profile that must be counted and
must raise no marker row — is UNPROVEN. It is landed, and it is recorded here
as unproven rather than dropped silently or written up as a proof that was
never obtained.

The cause is entirely outside this row. It is the only one of the four cases
that builds an actual calendar, so it is the only one that loads the registry
authority, and the concurrent authority-grade sweep has that load refusing.
Roughly two dozen attempts across the row, spanning several sweep rounds and
a window of well over an hour, refused every single time. The refusals came
in three shapes, all of them registry-authoring rather than surface faults: a
revision failing its own export-layout schema, because an export field
declares allowed values without the matching value policy; a set of revisions
whose declared authority grade outruns the families they have populated; and
the loader's own concurrency guard reporting the registry directory changed
during cache fingerprinting and asking for a retry once concurrent writes
settle. That third shape is the tell — the tree was being rewritten
underneath each attempt.

So the case has never been observed green, and an anti-tautology case never
observed to pass is not yet evidence of anything. Re-running this ONE test
once the registry sweep settles is what completes this row's coverage claim;
until then the claim is three cases proven and one landed-but-unwitnessed.

One incidental finding shapes the assertion and is worth recording: the bucket
id is REDACTED on this surface. An assertion embedding the registered id fails
against the redaction token. The candidate therefore matches the row by its
marker and the label it names. The original module's id-bearing expectations
could not have been carried over unchanged either.

## Notes

The row's scope path is WRONG and should be corrected for the next reader:
it names the module under the config package's test directory, and the module
has lived in the CLI package's own test directory since it was first added and
was never anywhere else. Time was spent hunting a file that never existed at
the stated path, and the real path belonged to another owner at the time, so
the correction is worth carrying rather than silently absorbing.

This row does not re-open the retired plaintext member's status, consistent
with the closed rows that settled it. The re-founded coverage writes no such
member — it needs none, because the incomplete state is a record state rather
than a directory shape — and the retired-member anchor in the custody
capsule-discovery module remains the naming authority. The refusal tests that
DO stage one keep staging it, unchanged, because that member's presence is
precisely the guard they assert.

Only ONE profile is registered per test here, and that is deliberate rather
than incidental. The live handover defect tracked elsewhere makes a second
registration in one process fail, so a fixture built the obvious way — a
workable profile beside an uncommitted one, which is how the ORIGINAL module
was written — would not run today. The single-profile shape is not merely
sufficient; it is the shape that works, and it is also the more honest one,
since the surface's classifier only ever inspects the active profile.

Two attempts to run the candidate under pytest from the scratchpad, before the
work was landed, failed on collection for environment reasons rather than test
reasons: the repository's session-scoped temporary directories were being torn
down underneath the run by concurrent peer sessions. That is why the
pre-landing proof used a standalone script; the post-landing verification runs
in the normal suite and did not hit it.

No commit was made and no plan checkbox was set. Every capture lives under the
session scratchpad rather than the repository.
