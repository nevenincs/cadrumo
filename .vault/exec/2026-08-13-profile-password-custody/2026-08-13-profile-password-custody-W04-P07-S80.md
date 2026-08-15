---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:4990ad8c0b44af417e0606f3e4d461c89ac586aadfb6374f78f060a0ea402b72'
step_id: 'S80'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore lane reachability for the eight keychain-marked tests placed where no keychain lane names them

## Scope

- `justfile and src/cadrumo/adapters/persistence/storage/master_key/tests/ and src/cadrumo/adapters/persistence/storage/tests/`

## Description

- Add the two storage test directories to the keychain lane's declared scope.
- Confirm the standing reachability gate goes green.
- Confirm the eight tests actually execute, and report anything they reveal
  separately rather than folding it in.

## Outcome

One line in the recipe: the keychain lane named three paths and neither of the two
holding these tests. The markers were already correct -- the lane simply did not
reach where this campaign's custody work had put them. No new mechanism, no
exemption, no marker change.

The standing reachability gate goes from red, naming exactly those eight, to
twenty-nine passing, verified independently.

And the tests now RUN, which is the part that mattered: six pass and two fail.
Both failures predate this change and were simply invisible while nothing
selected them. Neither is the host-credential-store case the recipe's own comment
anticipates -- six keychain tests pass here, so the store is genuinely reachable
on this host.

## Notes

The first exposed failure is the more serious, and it is a vacuous test on a
security-critical path. A receipt-tampering test expects an authentication
refusal and receives a malformed-record refusal instead. Traced rather than
guessed: the test tampers by re-encoding the receipt with a plain serializer,
which breaks byte-canonicality, and the canonical-bytes check refuses first --
returning through the malformed branch before the authenticated-data check is
ever evaluated. So production appears CORRECT, since an uncanonical record cannot
be authenticated and is still refused and cleaned. The defect is that the
tamper-detection path this test exists to cover **has never once been exercised**,
because the test never reached it and, until now, never ran at all. The remedy is
to tamper THROUGH the canonical encoder so the record stays canonical and the
authentication check is genuinely reached.

The second is a deterministic identity-anchoring refusal that reproduces alone in
seconds, so it is neither an ordering nor a parallelism artefact. A plausible
mechanism was identified -- anchoring on a storage root whose parent was never
materialised, where the passing siblings anchor on an existing path -- and
deliberately reported as PROBABLE rather than established, because it was
inferred rather than measured. Both are carried as their own rows.

That separation is the point of the step rather than an aside: folding either
finding into this fix would have re-hidden exactly what making the lane reach
them was for. A lane that reaches a test and then absorbs its failure is no
better than a lane that never reached it.

The commit's stat line was checked against intent before moving on -- one file,
one insertion, one deletion -- which is now standing practice after a
prose-only change elsewhere shipped as a hundred and nineteen deletions.
