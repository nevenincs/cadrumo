---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:9bd59959bcf61c8ea3ab40258a56de00d1484a80c4f700180564257917682754'
step_id: 'S190'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore the setup status to the profile listing payload, since a mid-setup profile now renders indistinguishably from a workable one, the listing carrying only name and identifier and active flag with no state and no advisory, while the advisory's catalogue key survives with no producer anywhere in the tree, so an operator cannot tell which of their profiles is unusable and the test that existed to prevent exactly this was rewritten onto a different subject

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py and src/cadrumo/application/workflow/_profile_bucket_scan.py`

## Description

- Establish what a profile listing can know about a LOCKED profile.
- Establish whether the orphaned advisory can be produced as its text promises.
- State the disposition rather than force a change that would break a gate.

## Outcome

**The row asks for something the encryption boundary forbids, and the boundary
is correct. Not implemented, deliberately.**

The complaint is accurate: the listing carries name, identifier and active flag
with no state, the advisory's catalogue key survives with zero producers
anywhere in the tree, and an operator therefore cannot tell from the listing
which of their profiles is unusable. All three were verified.

What does not follow is that the state can be restored there. Setup state lives
inside the profile's ENCRYPTED record. The only field readable while a profile
is locked is its label -- the capsule's label record is separately readable by
design, and nothing else is. So the listing cannot learn a locked profile's
setup state without that profile's passphrase, and the advisory's own text
promises a COUNT across profiles, which would require unlocking every one of
them in turn.

The second reason is sharper, because it is already written down as a decision.
The listing verb is bootstrap-exempt, and the stated ground for its exemption
is precisely that it decrypts nothing and needs no session, so that a locked
profile still lists and an operator can discover the label that login needs.
Adding a record read to the listing would falsify the exemption's own
justification and break the deadlock the exemption exists to prevent: the
answer would once again be reachable only once you already knew it.

So the honest disposition is that this must NOT be built as written. The
operator-facing need is real and is served elsewhere: the status and show verbs
both report setup state for the active profile, which is the profile the
operator is about to work with and the only one whose state is knowable.

**What the standing goal still asks for that this excludes.** An operator with
several profiles still cannot see, without unlocking each, which are
mid-setup. Closing that would require persisting a setup marker in the
plaintext capsule alongside the label -- a deliberate decision to publish one
more fact about a taxpayer outside the encryption boundary. That is an
operator's call about a confidentiality trade, not an implementation detail,
and it is not taken here.

## Notes

The orphaned catalogue key is left in place rather than deleted. It is
evidence of the decision, and its text is the specification a plaintext setup
marker would have to satisfy if that trade is ever accepted. Deleting it would
erase the only record that this capability was once intended.
