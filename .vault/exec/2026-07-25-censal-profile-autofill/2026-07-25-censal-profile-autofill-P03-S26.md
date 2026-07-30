---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S26'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Prove by execution whether the ownership guard reads a deliberately cleared identity as a first read, and close the adoption path if it does, a cleared identity being an operator decision rather than an absent one

## Scope

- `src/cadrumo/application/user_profile/_censo_sync.py`

## Description

- Establish by execution whether the ownership guard reads a deliberately
  cleared fiscal identity as a first read rather than as an operator decision.
- Close the adoption path it opened, refusing a censal read when the profile
  records no fiscal identity at all.
- Cover both routes to that state, since a never-recorded identity reaches it as
  readily as a cleared one and an allowance for the first would have left the
  door open.

## Outcome

A censal read is refused when the active profile records no fiscal identity,
whether the identity was removed or never set. The guard no longer treats an
absent identity as a first read to be adopted onto.

Landed as commit `d966d2e4a0`, touching the censal sync module and its tests.
Re-verified at this reconciliation: the censal sync suite passes at 29.

## Notes

Scaffolded and first drafted during a plan reconciliation; the executor then
authored this account, so the reasoning below is first-hand rather than
reconstructed from the commit.

The step asks for proof before change, and that ordering was load-bearing rather
than ceremonial. The cleared-identity hole was reachable by execution before
anything was written, which is what distinguished it from a reading of the code
that might have been wrong about the world.

The step reopened after an initial disposition. The first framing would have
refused only a cleared identity and allowed a never-recorded one, on the reading
that a profile with no identity yet is mid-setup and adopting onto it is
harmless. That leaves the same door open by the other route: both states present
identically at the guard, and neither can be confirmed to belong to the taxpayer
the read describes. Refusing on absent as well as cleared is what closes it, and
the two branches carry distinct refusals so an operator is told which state they
are in rather than being given one message for two situations.

The premise worth recording, because it was the thing that could have made the
stricter reading wrong: no setup or wizard path invokes the pull. That was
verified rather than assumed, so removing the first-read allowance cannot block
profile creation.

The mutation proof was run in both directions and re-run after the tests changed
shape, rather than carried forward from the earlier run. Restoring the never-set
allowance reds exactly two tests; collapsing the cleared branch reds two others;
the populated-and-matching case stays green throughout, so a guard that refused
everything would also fail.

This half of the protection is not the whole of it. A profile still in setup is
deliberately allowed to authenticate, so the refusal that covers that case lives
with the read rather than with the session bind.
