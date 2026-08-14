---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:25dfd5b924f9bcc47172790a9b8f5a9a05b64549c9d5aa333a24a725d53dc09c'
step_id: 'S51'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule which contract governs the retired profile's session receipt

## Scope

- `src/cadrumo/application/user_profile/_login_session.py and src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py and src/cadrumo/application/user_profile/tests/test_login_handover.py`

## Description

- Determine empirically what the retired profile's surviving receipt is worth,
  by asking the production resume authority rather than by reading the code.
- Rule whether the two intentions genuinely conflict.
- Close the route and prove the closure on recovered key material, not on file
  absence.

## Outcome

The framing this step was dispatched with was wrong, and correcting it is the
finding. It was posed as two deliberate intentions in conflict needing
adjudication -- preserving evidence when the keychain is unreachable, against the
guarantee that a retired profile cannot resurrect. There is no conflict. The two
are already separated by path and correctly so: explicit revocation clears the
receipt unconditionally, while evidence preservation lives only in an incidental
cache-miss evaluation where retaining an unusable receipt is right.

The defect is that the handover path never invoked revocation at all. It closed
the retired profile's two in-process handles and stopped, while the authority
whose own documentation calls it the single authority for a profile no longer
being logged in was composed by logout and by custody deletion, and not by
handover -- although the module docstring already claimed it was.

The severity was established by demonstration, not argument. Driving a real
handover through the production login path and then asking the production resume
authority for the retired profile returned a resumable session and its
thirty-two byte bucket key, WITH NO PASSPHRASE, after the handover that was
supposed to retire it. Neither the custody-change nor the missing-keychain-entry
arm fires, because handover rotates neither generation nor epoch and revokes
nothing. This was the most serious defect the campaign has produced.

It is not a regression from the commit first suspected: the retirement function
is byte-identical across it, and the failing assertion existed in the same form
beforehand. Nothing needed overturning.

Verified independently: 27 passed, including the three that were red.

## Notes

The fix deviates from the one approved, for a reason that had to be found by
building it. Calling the revocation authority directly would have BROKEN the
handover: that authority begins by closing whichever record session is currently
active, and at the retirement point the active session is the newly promoted
profile's. The approved fix would have torn down the profile the handover had
just promoted.

So the durable half -- deleting the on-disk record and its keychain key, clearing
the login backoff -- was split into its own module-private function, which the
strong close composes after its process teardown. The handover calls the durable
half only, because it already closes the retired profile's process authorities by
identity, which is more precise than a global teardown. One implementation, two
composers, no second copy.

The revocation is guarded on the predicate for whether the handover actually
changed bucket. That guard is load-bearing rather than defensive: on a same-
profile re-login the predicate is empty, and revoking there would destroy the
receipt that very login had just minted.

The regression asserts the recovered key material is absent, not that a file
vanished, and carries its own anti-tautology arm proving the receipt IS resumable
while the profile is live -- so it cannot pass against a profile that never had
one. Logout and custody deletion were both re-confirmed end to end, since the
split added a second composer.

The change reached HEAD inside another campaign's commit about sweeping the
operator help surface, which consumed the working-tree files within about ninety
seconds of the tests going green. The condition that a security fix be legible in
history under its own description was therefore not met, and this record carries
the account instead. Rewriting another campaign's landed commit to recover the
attribution would be a history rewrite, disproportionate to a defect that is
fixed, verified and documented here.
