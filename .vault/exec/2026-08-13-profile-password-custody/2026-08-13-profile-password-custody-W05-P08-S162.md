---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e5caf9f7a7c9b6447968dd7263c7adb90461fa20febb01c875b5cb1098b1449d'
step_id: 'S162'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh establish whether an out-of-process test can reach a profile provisioned through the surviving in-process creation door, since twenty-four subprocess tests assert on a return code from a CLI that now refuses to create a profile on a console-less host, leaving cold-process behaviour untestable end to end, and no new production creation path may be built to answer it

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Drive the existing in-process creation door in setup, hand the storage root
  to a subprocess, and observe each hop.
- Establish what blocks rather than designing around it.
- Build no new production creation path.

## Outcome

**The unlock is not the blocker. It works.** A profile created through the
in-process credential door into a temporary root is reachable from a
subprocess: the passphrase crosses the process boundary through its sanctioned
environment variable, and login succeeds with a zero exit and the profile
selected. Reading the profile's status from that subprocess also succeeds.

That answers the half this row was written around. The concern was that the
passphrase demand -- the entire point of custody -- would have no route out of
process, and it does have one.

**What blocks is narrower and is a defect rather than a consequence of the
retirement.** Reading the profile RECORD from the subprocess refuses with
`missing_profile_record`. The identical command, on the same profile, against
the same storage root, run in-process, returns zero and reports the record
VALID.

**So the record is not missing, not unwritten, and not locked -- it is
invisible across the process boundary, and the refusal names the wrong cause.**
A diagnostic asserting a record is missing, about a record that reads as valid
moments earlier in another process, is worse than a plain failure: it sends
whoever reads it looking for something absent instead of for a boundary.

**The loss is therefore partial rather than total.** Cold-process tests that
need a profile to exist, to be selected, or to be logged into are reachable
today with a fixture that creates in-process and hands over the root -- no new
door, no production surface, nothing re-implemented. Only the subset that reads
the profile record is blocked.

## Notes

No fixture is proposed yet, deliberately. If record reads are meant to cross
the process boundary then the defect's repair removes the need for one at those
sites; if they are not, that is a documented limit and a fixture would serve
only the sites that never needed it. Proposing the fixture first would have
buried the defect underneath it.

The probe is the artefact rather than the prose: seven hops, each printing its
own result, ending with the in-process and out-of-process reads of the same
record side by side. That pairing is what converts "cold-process tests are
untestable" into a statement naming the exact hop that breaks.

**This is the third defect surfaced by making a dead path reachable**, after a
surviving edit verb that crashes on an event type absent from its own enum, and
a requirement enforced only by a retired path. None of the three was visible
while the fixture could not be built, which is the argument for building the
fixture before concluding anything about what the tests can no longer prove.
