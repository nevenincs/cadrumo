---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:5af124e74a47ddec0ad2d1e15d26bb48527f5524c6f82cc701958e7efdc2b1d0'
step_id: 'S193'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Terra XHigh retire the displaced profile's session material inside the registration transaction itself, since registration selects the new profile by pointer compare-and-swap and retires nothing, so the previously active profile keeps a resumable acceleration receipt until some later login happens to observe the boundary, leaving its bucket key recoverable with no passphrase across the whole window and permanently for a registration no login ever follows, which is the same leak the handover revocation was rebuilt to close reached through the creation door instead

## Scope

- `src/cadrumo/application/user_profile/_custody_service.py and src/cadrumo/application/user_profile/_registration.py`

## Description

- Measure the creation-door leak across separate processes before forming any
  conclusion about it.
- Retire the displaced profile inside the create transaction, ahead of the
  pointer compare-and-swap, through the existing revocation primitive.
- Name the displaced profile from the durable pointer witness the transaction
  already journalled, not from the live session and not from the handover
  journal.
- Honour the removal's outcome, and give the refusal an account the operator can
  act on.

## Outcome

**The leak is real and was measured at thirty-two bytes.** With the create
transaction's retirement removed -- injected out from a startup hook outside the
repository, so it reaches the spawned children too -- a profile is registered, is
logged into in its own interpreter, and is then displaced by a second
registration in a third. Asked in a fourth process for the displaced profile's
material with no passphrase, the production resume authority returns a full
`dek_length` of thirty-two. With the retirement live the same probe returns zero,
`resumed` false, and the typed absent refusal. No login runs between the
displacement and the probe, which is the whole point: this is the window the
login-side retirement can never reach, and for a registration no login ever
follows it never closes at all.

**Retirement happens inside `_publish_verified_create`, strictly before the
compare-and-swap, on both of its swap branches.** Ordering it ahead of the
pointer move is what makes the property crash-proof without inventing a second
durable state. A process death between the two can leave the retirement done and
the pointer unmoved, which costs the operator one passphrase; it cannot leave the
pointer moved and the receipt live, which costs a passphrase-free bucket key.
Bolting the retirement on after the transaction returned would have reinstated
exactly the torn window the row exists to close.

**The identity comes from `pointer_before`,** the durable pointer value the
create transaction captures under the custody lock and journals before it stages
anything. Neither identity a fresh process can otherwise reach is honest here,
and the closed union row had already established why: the live in-process session
is absent in the ordinary operator flow, where every invocation is a new process,
and the handover journal is written from that same live value, so both are blank
in precisely the case that leaks. That is not an inherited assumption here -- it
was re-measured. A second injection keeps the retirement call exactly where it
is and changes only where the profile is named, deriving it from the live bucket
session; the leak returns at the full thirty-two bytes.

The removal itself is the one the delete transaction already uses, so no second
implementation of "this profile's stored session is void" exists to disagree with
the first. A pointer naming something that is not a profile UUID is passed over
rather than refused, because registering a fresh profile is the operator's route
out of a corrupt pointer.

**The removal's outcome is honoured, and honouring it exposed a second defect
that this row created and has fixed.** The primitive verifies the artefact is
gone and raises when it is not; the create transaction converts that into a
refusal rather than swallowing it, and because the refusal is raised before the
swap the pointer stays on the profile that could not be retired. That much was
sound. What was not: the refusal travelled as the generic create conflict, and
the registration door renders every create conflict as "profile '%{label}'
already exists". Measured rather than assumed -- occupying the receipt path so
the removal cannot complete, an operator registering a brand-new profile was told
the label they had just chosen was taken. The retirement refusal now carries its
own error type and its own message in all four catalogues, caught ahead of the
collision branch. The type subclasses the conflict deliberately: every handler
that treats a create conflict as a pointer-preserving refusal must keep catching
it, so narrowing the message must not narrow the catch.

**Three separate-process proofs, plus the direction that would otherwise pass
silently.** After a registration that displaces an active profile, the displaced
profile yields no key material in a fresh process. The anti-tautology arm proves
the same probe does return the full thirty-two bytes while that profile is
legitimately selected, so the refusal cannot pass merely because another process
cannot reach the material at all. A registration that displaces nothing -- the
very first one, with no pointer to read -- still publishes its profile and is
still loginable. The fourth pins the opposite direction: a retirement that
resolved the wrong identity would satisfy the non-resurrection proof while
destroying the session of the profile the operator just created, so the entering
profile's own receipt is proved to survive.

**Three injections, each from outside the repository, each reddening only what
should react.** Removing the retirement reds the non-resurrection proof alone,
and reds it on recovered key material rather than on a reported outcome. Deriving
the identity from the live session reds the same single case on the same
material. Routing the refusal back through the generic conflict reds only the
refusal case, and reds it on the account the operator receives. The obstruction
in that last proof is a real filesystem state -- the receipt path occupied by a
non-empty directory -- rather than a patched function, so it holds on any
platform, and its unobstructed control is the displacement proof at the top of
the same module.

**Verification.** The whole user-profile package runs 373 passed and 13 failed
sequentially, in twenty-six minutes; parallel workers were not used, because that
package has hung past eight minutes on this share. The retirement suite is five
passed on its own. The login-handover suite, the sequential-registration suite
and the crash matrix are all green in that run -- not one of the thirteen
failures is in them, in the retirement suite, or in any file this row touched.
The error-code registry gates are fifty-four passed, which is the gate the new
error type has to satisfy. Formatter, linter and the canonical type checker are
clean on every changed file.

## Notes

**The row's own premise was confirmed rather than assumed, and one part of the
brief turned out to be stale.** The brief described a previous dispatch cut off
with no source changes; in fact its production change and its suite had already
reached the branch inside a peer session's broad sweep commits, which is the same
working-tree capture two earlier rows in this campaign recorded. Nothing was
re-implemented on top of that. What this session added is the measurement the row
demanded and had never been recorded, the two identity and refusal bite proofs,
the operator-facing refusal repair, and this record.

**Three files outside the row's named ownership were touched, each a
precondition rather than a widening.** A `CadrumoError` subclass cannot exist in
this tree without a declared error-code entry -- the class raises at definition
time otherwise -- so the new type is declared in the application error-code
registry shard. A new `translated_message` key needs a real value in all four
locale catalogues, which were written through the `dev.locales` CLI rather than
by hand. Nothing in `_login_session.py` or `_profile_pointer_transaction.py` was
edited.

**Ambient red, attributed and not absorbed.** Every one of the thirteen
package failures resolves to a cause outside this row. Three are a peer's
changed `register_minimal_profile` signature, raising a positional-argument
TypeError. Four are the registry authority failing to load tree-wide from a
concurrent sweep -- modelo 122's revision carries two validation errors, and
modelo 341's `semantic_role_cardinality_reason` exceeds its 256-character bound,
which also errors the locale parity gates at setup. Four are CLI surface: the
settled retired wizard-creation door, and three verbs the surface no longer
carries. One is the declared-writers scan naming a CLI manager module. One is an
English assertion against Spanish output, which is the default-language flip an
earlier row in this campaign already attributed. The locale scaffold check
reports 835 missing and 23 extra keys identically in all four catalogues, every
one a modelo-schema or CLI-help key, and none the key added here, which the same
check confirms present in all four. One spawn child exceeded its queue timeout
during a loaded injection run and passed on re-run with no code change, which is
the share rather than the code.

**A live defect in the immediate neighbourhood was left alone deliberately.** A
logged-in profile cannot currently be deleted; that belongs to its own row and
was neither absorbed nor worked around here.

**The plan row is deliberately left open and no git write of any kind was made.**
