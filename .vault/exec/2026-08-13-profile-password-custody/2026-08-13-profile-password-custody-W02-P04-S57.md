---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b82b705b32ba843fbbacffe6e6ef1842163a897cc7ee85ca27673244beeeeb72'
step_id: 'S57'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh stop the auth session fallback raising where it is documented to degrade

## Scope

- `src/cadrumo/application/auth/_sessions.py and src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py`

## Description

- Establish whether the fallback branch is obsolete under per-profile custody or
  merely mishandled, before writing any fix.
- Verify the degradation now holds at both sites with a profile created the way
  production creates one.
- Record what coverage the closure does and does not carry.

## Outcome

Closed as delivered by consequence, and the reasoning is the point rather than
the outcome. The question the row could not answer was whether the branch was
mishandled or obsolete. It was OBSOLETE: it reached for a shared-master provider
that, under per-profile custody, could open a bucket with no password at all and
would answer for a taxpayer's profile through a second custody lifecycle beside
the capsule that owns it. So the right repair was never catching a second
exception type -- it was deleting the branch, which the port-collapse sweep has
now done at both sites.

The mechanism needed BOTH halves closed and both are. The fallback is gone, and
separately the record reader now raises only the not-found refusal in every
failure mode, so the error type the handlers catch is the only one the reader can
produce. Either alone would have left the defect reachable.

Verified with a profile created through the credential-registration door, which
is how production creates one -- so it holds a random per-profile custody key and
no master-key-wrapped bucket key, the exact shape the row says the fallback could
not read. Authenticated, the reader returns the taxpayer's facts; registered with
no session, it returns empty authority facts and reports the profile record as
locked rather than borrowing the absent-identity token. Degradation, not a raise.

Independently confirmed: zero non-test references to the provider remain in the
application layer, the entry points, the domain, the core or the outbound
authority adapter.

## Notes

Coverage is asymmetric and that is the residue. The application half is properly
pinned by a test that names this exact mechanism in its documentation and seeds
one record to read it twice, so the sealed read is not tautological. The
identity-provider sibling has NO coverage at all.

An attempt to pin it found a blocker larger than the row: that adapter's test
package carries an always-on fixture which writes the retired bucket manifest,
and capsule discovery refuses any root containing one. So no test in that package
can seed a current capsule, and anything needing an active bucket trips it on the
pointer read -- leaving only the no-active-profile arm, which alone is too weak
to be worth having. The package cannot currently host capsule-backed coverage of
its own code.

That blocker was left untouched deliberately: changing an always-on fixture the
whole package depends on, while the ruling on which layer owns that manifest is
still in flight, would pre-empt a decision that is not this row's to make. It is
carried as its own row, sequenced behind that ruling.

No red was left behind: the attempted test was removed rather than committed
half-passing.
