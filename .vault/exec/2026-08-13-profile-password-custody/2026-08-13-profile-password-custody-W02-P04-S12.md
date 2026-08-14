---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4332824cf0d7b8d0b980d5a9916e5cb1a225678a4d4bc14f412d4663a918fb48'
step_id: 'S12'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium review candidate namespace cleanup, atomic in-process handover, B session promotion, keyring failure, post-swap recovery, and A non-resurrection

## Scope

- `src/cadrumo/application/user_profile/_login_session.py and src/cadrumo/adapters/persistence/storage/custody/`

## Description

The phase review returned FAIL with two HIGH findings. This record covers
their remediation and the re-verification, not a second review pass.

- Confirm the retired shared-master provider is gone from live user-profile
  composition: no provider protocol, ambient key resolver, or global recovery
  facade is named by any production module under the profile package.
- Add a structural absence gate over that package, with an anti-tautology proof
  that the name scanner reds on a module which does use the retired surface, and
  an anchor asserting the forbidden names are defined only in the retired
  package so a rename cannot make the gate pass vacuously.
- Split the local-record read primitive under overloads so a non-optional read
  is typed as returning bytes and only the explicitly-optional read may return
  none, preserving the existing fail-closed runtime refusal.
- Promote the pending label-advance witness to its canonical public model owner,
  removing the private cross-module dependency the review flagged.
- Give the shared canonical-payload digest a purpose-built name on the module
  that owns it, so the hold-evidence models no longer reach into private
  helpers.

Two conditions blocked verification and were closed as in-scope absorption.

- Complete the retired recovery-facade deletion the phase had started: its
  re-exports still bound both storage facades, so importing the storage package
  raised a missing-module error and no gate in the tree could run at all.
- Retarget the test seeding left behind by the discovery phase. One hundred and
  seventy-six modules still imported four application symbols the phase
  deleted; they now compose the current capsule helpers, with a fact-upsert and
  an active-profile fact helper added to carry the retired plural fact command.

Restore the schema judgement on profile facts, which the capsule cutover left
without an owner. Registration wrote its initial facts unvalidated and the
record patch door did the same, so a value at an engine-derived path could be
stored and displace the calculation that owns it; the only surviving check sat
in the manager's edit dialog and bound nobody writing through another surface.

Re-point three gates that had gone vacuous: the console-less secret-channel
proof, the two censo single-authority pins, and the stale taxonomy and
deferred-import declarations.

## Outcome

Both HIGH findings are closed.

Scoped strict type checking over the custody adapter, the profile package and
the wizard package reports zero errors, zero warnings, against twelve errors at
review time. Collection over the whole tree reports no error attributable to
this campaign, against one hundred and ninety-four before; the eighteen that
remain are a concurrent registry review-status campaign's and are recorded
below rather than attributed here.

The absence gate, the redesigned atomic-create rollback proof, the derived-path
write refusal, and the taxonomy and deferred-import declarations all pass.

## Notes

Two properties were lost by the cutover rather than by this step, and are
carried forward as tracked rows rather than closed silently.

The successor custody surface returns unwrapped key material as an immutable
value, where the retired facade returned a mutable buffer the wipe primitive
could reach. The wipeability tests were bound to the deleted facade and went
with it, so the property is currently unproven anywhere. A new step carries
restoring it before the final security proof.

The write-door judgement restored here was verified at the two doors this step
could see. A second new step carries an independent audit of every write door
for judgement parity, because a surface-only pre-check was exactly the shape
that let this gap survive unnoticed.

External and unattributed: a concurrent campaign leaves several modelo
revisions and legal references below filing-grade review status, which fails
eighteen collections; and the taxonomy literal detector no longer recognises a
token a peer removed from the storage taxonomy, which reds that gate's own
anti-tautology case together with three declarations in storage-campaign
modules. Neither was touched here.
