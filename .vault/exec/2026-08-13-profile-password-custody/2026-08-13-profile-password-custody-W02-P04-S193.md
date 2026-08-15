---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:12e4dd855c032d3a6f30a997c9ce9b64f95dcc7c988106bcd9647018cbe91213'
step_id: 'S193'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh retire the displaced profile's session material inside the registration transaction itself, since registration selects the new profile by pointer compare-and-swap and retires nothing, so the previously active profile keeps a resumable acceleration receipt until some later login happens to observe the boundary, leaving its bucket key recoverable with no passphrase across the whole window and permanently for a registration no login ever follows, which is the same leak the handover revocation was rebuilt to close reached through the creation door instead

## Scope

- `src/cadrumo/application/user_profile/_custody_service.py and src/cadrumo/application/user_profile/_registration.py`

## Description

- Measure the leak across separate interpreters, from outside the repository,
  before changing anything.
- Retire the displaced profile inside the create transaction, ordered strictly
  ahead of the pointer compare-and-swap.
- Resolve the displaced identity from the durable pointer value the transaction
  journalled, not from the live session and not from the handover journal.
- Delegate to the one revocation primitive the delete transaction already uses.
- Prove the property, its anti-tautology arm and its opposite direction across
  separate processes, and bite-prove both the retirement and its identity source.

## Outcome

**The leak was real and is measured on both sides: thirty-two bytes before, zero
after.** In separate interpreters against an isolated real storage root --
register a profile, log into it, register a second, then probe the first -- the
production resume authority handed back the first profile's full thirty-two byte
bucket key with no passphrase, resumed true and no refusal. The same sequence
after the change returns zero bytes with the typed absent refusal. The
anti-tautology arm was measured in the same run and in the same configuration:
while the first profile is still the selected one, the identical probe recovers
thirty-two bytes, so the refusal cannot be an artefact of a separate process
being unable to reach the material at all.

**The retirement lands in the create transaction's publication step, in the
statement immediately before the compare-and-swap.** That ordering is the whole
of the crash-safety argument, and it is why no new durable state was needed: a
process death can leave the retirement done and the pointer unmoved, which costs
the operator one passphrase, but it cannot leave the pointer moved and the
receipt live, which costs a passphrase-free bucket key. Recovery re-enters the
same publication step and re-derives everything from the journal, so a resumed
transaction retires before it swaps exactly as a first attempt does. Both
branches that leave the pointer naming the new capsule run it; the branch that
refuses an independently changed pointer deliberately does not, because that
create is being rejected and the profile it would have displaced is still
legitimately selected.

**The identity comes from the pointer's previous value, journalled before the
swap.** The create transaction already captures the durable pointer under the
custody lock when it writes its journal, and persists it. That is the only
honest source available here. The live in-process session is absent in the
ordinary operator flow, where every invocation is a fresh process, and the
handover journal is written from that same live value, so both are blank in
precisely the case that leaks -- the trap the earlier revocation row marked in
advance, and it was not rediscovered. Nothing new had to be persisted to make
this work, which is worth stating plainly: the transaction was already recording
the fact needed to close the hole and simply was not reading it.

**One revocation implementation, not two.** The retirement calls the same
session-acceleration revocation the delete transaction calls, which is itself
composed over the single authority the login handover uses. That primitive
deletes the on-disk session record and its paired keychain key, then verifies
the artefact is gone and raises when it is not. The refusal is converted into
the create transaction's own conflict type rather than swallowed, so a
retirement that did not complete refuses the registration with the pointer still
on the displaced profile -- the fail-closed direction. This answers the
discard-outcome trap structurally: there is no boolean to ignore, because the
primitive was already rebuilt to raise.

**Four committed proofs, every operator step in its own interpreter.** A
registration that displaces a logged-in profile leaves it with no recoverable
key material, probed before any further login, which is the case the login-side
retirement can never cover. The anti-tautology arm proves the same probe does
recover the key while the profile is selected. A registration with no
predecessor still publishes its profile and authenticates. And the opposite
direction is pinned: after the displacement the entering profile authenticates
and its own receipt resumes, so a retirement that resolved the wrong identity
would red rather than pass. The new module is four passed on its own.

**Two bite proofs, both from outside the repository through a startup hook.** A
plugin does not reach a spawned child and the registration under proof runs in
one, so the injection rides on the interpreter's startup path instead; nothing
under the source tree was modified in either. Disabling the retirement reds
exactly the displacement case, on the recovered key material rather than on a
reported outcome, and leaves the other three green. Replacing only the identity
source with the live in-process session -- the trap, with the retirement itself
fully intact -- reds exactly the same single case. The suite therefore
distinguishes the durable pointer from the live session, rather than passing on
any retirement that happens to run.

**Verification.** The whole user-profile test package ran sequentially under the
union marker, because the default selection would have executed none of these
integration modules and printed green: 369 passed, 13 failed, in eleven minutes
forty. Every failure is attributed and none is in a module this change touches
-- login handover, sequential registration, registration, custody transactions,
capsule lifecycle, restore atomicity, logout strong close, atomic create
rollback and destroy-reaps-session-artefacts are all green. Two atomic-create
roundtrip cases refuse on CLI verbs that no longer exist; three first-run
surface cases refuse on the settled retired wizard-creation door and on the same
absent verb family; four cases across requirement rendering and profile services
die on the tree-wide registry validation failure left by the concurrent
authority-grade sweep; three language-resolver cases die on a shared test
helper's signature changing under a peer's in-flight sweep of the registration
door; and one adoption-policy case names a CLI frontend module a peer added
without declaring it. Type checking and lint are clean on both changed files,
and the tree-wide type gate reports no diagnostic naming either of them.

## Notes

**The registration module needed no change and was left alone.** The row scoped
both the transaction owner and the credential door. The credential door is a
thin caller: it stages material and delegates to the lifecycle, which delegates
to the transaction. Adding the retirement there would have been the second write
beside the transaction that the row and the architecture rule both forbid, and
it would have re-created the torn-write window the transaction exists to remove.

**The fix reaches the restore door too, and that is correct rather than
incidental.** Restoring a capsule publishes through the same create transaction
and selects the restored profile the same way, so it displaces whatever was
selected and now retires it on the same terms.

**One deliberate non-refusal, argued rather than silent.** A pointer whose value
is not a profile identifier owns no session artefacts, because those are keyed
by identifier, so there is nothing to retire and nothing to leak. It is passed
over instead of refused, because registering a fresh profile is the operator's
route out of a corrupt pointer and blocking it would turn a recoverable state
into a dead one. A pointer that is not canonical at all still refuses, unchanged.

**A duplicate decode was folded rather than added to.** The delete path already
decoded the captured pointer to decide whether to clear it, and the new identity
lookup needed the same decode. The two now share one implementation instead of
the transaction owner carrying two parsers of the same bytes that could disagree
about what a malformed pointer means.

**One red inside the new suite was investigated rather than absorbed.** The
first bite run reported a second failure, on the anti-tautology arm, which is
structurally independent of the injection: it performs no displacing
registration at all. Re-running that case alone under the same injection passed,
and re-running the whole injected batch reproduced the single expected failure
with the arm green. It is run-to-run instability of the spawned-interpreter
setup on this share, not a property of the change, and the conclusion was drawn
from the reproduced run rather than from the first one.

**The changed files reached the branch inside a peer session's broad sweep
commit while the verification runs were still in progress.** This session ran no
git write of any kind. The landed content was re-read from the committed tree
afterwards and is byte-identical to the working tree: the retirement, its
identity lookup and the new suite are all present and unmangled. As with the two
earlier rows that recorded the same capture, the condition that a custody fix be
legible in history under its own description is not met, and this record carries
the account instead.
