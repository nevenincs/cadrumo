---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:30f80c0e8d0ff5a187ccf49a7fba80d83cb3dbd37597d4d70f424652584aa6af'
step_id: 'S12'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium review candidate namespace cleanup, atomic in-process handover, B session promotion, keyring failure, post-swap recovery, and A non-resurrection

## Scope

- `src/cadrumo/application/user_profile/_login_session.py and src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Review the handover phase against its declared properties, with the
  non-resurrection guarantee as the central one.
- Re-run after each refusal rather than closing on the prior reviewer's evidence.
- Prove the property by mutation rather than by a passing suite.

## Outcome

**Closed on the third review.** It was closed once on false evidence, reopened,
refused once on true evidence, and has now passed on evidence the reviewer
generated rather than accepted.

The first closure was false because a gate derived its expected scope from its own
scan root and therefore agreed with itself at any width. The second review refused
and found the central property measurably false: the handover derived the profile
to retire solely from the live in-process session, so in the ordinary operator
flow -- every command-line invocation being a fresh process -- revocation never
ran and the retired profile's bucket key stayed recoverable with no passphrase in
four of five crash phases.

The third review proves that closed by MUTATION. A probe spawning three
interpreters measures the retired profile's recoverable key material; at the
current tree it is refused, and with the pre-fix derivation reinstated in the
child it returns a thirty-two byte key and reproduces the second review's tell
verbatim. So the fix is load-bearing rather than coincidental.

**The decisive check was the proof's TOPOLOGY, not its assertions.** The first
closure survived because a well-written test asserting on recovered material ran
both logins in ONE process -- the single configuration in which the broken fix
worked. The regression now spawns real separate processes and asserts against the
correct artefact of the three that share the word "session". Injecting the
pre-fix derivation through an import hook reaching every spawned child reds five
of seven cases and leaves green exactly the phase whose retirement had already
completed -- the same leak profile the refusal measured, which proves the gate now
fails on the defect it previously could not see.

Green at close, sequential with markers disabled: the handover module at
twenty-eight, the crash parametrisation across five separate runs, the custody
package at forty-four, and the type checker clean over both scopes, which keeps
the first audit's second finding closed.

## Notes

The two traps that had cost earlier rounds were both handed to the reviewer in
advance and both were confirmed as traps rather than defects: the live-session
line that reads as the gate but is one of three inputs, and the one word naming
three artefacts in different custody classes. The reviewer re-read the module
after a vocabulary rename landed mid-review and confirmed by filtered diff that
the rename touched no retirement symbol, so its measurements held.

One medium finding is carried forward, outside this step's declared scope: the
receipt-revocation entry point discards a clear outcome that its sibling already
honours, so a refused clear is silent and a login can report a profile closed
while its receipt survives. Narrow reachability, but the campaign's signature
shape and the reporting value already exists.

The crash-phase flake recorded by the refusal did not reproduce across five
sequential runs and its mechanism is closed in source. The single red observed
during review was a peer's half-landed edit failing on an undefined name.

Worth recording about the process rather than the code: this step consumed three
reviews, and the two that produced real findings were the ones told explicitly
that refusing to close was the better outcome if it were true. The first review
was not given that instruction.
