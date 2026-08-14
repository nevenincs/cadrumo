---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0f8c311d17d4b204944f226af8117280dedd248c7e15405e66d76014163b7efe'
step_id: 'S72'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the settings-override test control its own environment instead of inheriting the operator's

## Scope

- `src/cadrumo/core/tests/test_config_override.py`

## Description

- Establish the absent-passphrase precondition the assertion always meant to
  read, rather than inheriting whatever the host provides.
- Isolate at the test, leaving the harness bridge untouched.
- Verify hermeticity across environment arms rather than against this host alone.

## Outcome

The test now establishes its own precondition through a local context manager
that removes the variable, drops the settings cache, and restores the prior value
on the way out whether or not the body raises.

The baseline is NOT relaxed, and the easier wrong answer was available and
rejected explicitly: capturing whatever was ambient and asserting a return to
THAT would have gone green on every host while converting a real absence check
into a tautology, passing on a machine with a passphrase configured while proving
nothing about absence. The assertion is unchanged; what changed is that the test
now establishes the condition it was always asserting about.

Three deliberate choices, each rejecting a shorter route. Not the patching
fixture, which a shipped gate bans outright and which prescribes exactly this
context-manager shape. Not the settings-override helper, which would have been
the shortest path to green and the wrong one, because it proves the override
mechanism that is itself the subject under test. And the cache drop is
load-bearing rather than defensive -- the constructed settings are memoised, so
removing the variable alone would leave earlier-built settings answering from
before the removal and the variable would appear inert.

Verified across three arms, which is what distinguishes hermetic from
passing-here: passphrase present via the harness bridge, explicitly absent, and
explicitly set to a probe value. All pass. The neighbouring module passes
alongside it, confirming the restore does not leak.

## Notes

The harness bridge was examined and found correct: it exists so integration paths
see real configuration, and the defect was one unit test reading ambient state it
never established. Narrowing the bridge would have traded a local red for a
silent loss of coverage elsewhere.

The bite proof carries an honest caveat rather than an overstated claim:
replacing the isolation with a no-op reproduces the original failure ON THIS HOST
because this host has a passphrase configured, while on a clean runner that arm
would still pass for want of anything to leak. The proof is host-appropriate
rather than universal, and the third arm is what covers the general case.

The wider consequence is recorded because it affects every number this campaign
collected: this failure was a phantom introduced by no commit, appearing only on
machines with an operator passphrase, so failure counts taken on developer hosts
must be discounted accordingly. It is the third measurement failure mode found in
one session, after selection markers silently deselecting whole modules and
carriage returns in generated path lists making a run verify nothing, and the
only one that lies in the RED direction rather than the green.
