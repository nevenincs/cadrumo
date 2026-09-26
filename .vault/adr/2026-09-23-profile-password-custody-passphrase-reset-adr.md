---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:0ea7c947ac2ce38a5b739d23a4abf225655f1ecbae79582ff4364ddf643645c5'
related:
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-09-23-profile-password-custody-passphrase-reset-reference]]"
  - "[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]"
---

# `profile-password-custody` adr: `Recovery passphrase reset` | (**status:** `proposed`)

## Problem Statement

`config passphrase reset` replaces a forgotten profile passphrase by proving the enrolled recovery code, and it ships. No decision accepts it: `2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr` deferred recovery-based reset as "a separate archive/lineage decision", and `2026-08-13-profile-password-custody-rollup-adr` repeats the deferral. This record makes that decision: what a recovery-authorised replacement does to archives, the envelope lineage, the audit record, live sessions, the recovery record and attempt throttling. The implemented behaviour, and its gaps, are grounded in `2026-09-23-profile-password-custody-passphrase-reset-reference`.

## Considerations

- Recovery is optional and independent of password authority (`2026-08-13-profile-password-custody-rollup-adr`, § Optional recovery).
- The reset re-wraps the same DEK and holds its epoch, so it revokes nothing the DEK already protects: pre-reset archives and copies stay openable with the passphrase they were made under, and the recovery code stays valid (reference, § Archives and § Recovery record).
- DEK rotation is unsupported (rollup ADR, § Constraints), so no replacement of a passphrase can be a compromise remedy today.
- A recovery-authorised reset is indistinguishable from an ordinary rotation in every persisted record, and the envelope chain field is never populated (reference, § Lineage and § Audit record).
- Failed reset proofs are not throttled, unlike login (reference, § Throttling).

## Considered options

- **Adopt the shipped reset as a forgotten-passphrase capability and close its gaps:** chosen. It keeps the operator's only route back into a profile whose passphrase is lost, which is the reason optional recovery exists.
- **Re-key on reset (new DEK epoch, re-encrypt, invalidate archives and recovery):** rejected. It needs DEK rotation, which is unsupported, and cannot reach archives already copied off the host; it would be a separate, larger decision.
- **Withdraw the command:** rejected. Enrolled recovery would then protect nothing a forgotten-passphrase operator can use.
- **Consume the recovery code on use and require re-enrollment:** rejected for now. The enrollment contract promises a reusable code, and consumption leaves the profile without recovery until the operator re-enrolls; replacing a code remains available through `recovery disable` then `enable`.

## Constraints

- The reset must stay bootstrap-exempt: the target profile is by definition one nobody can log in to (`src/cadrumo/entrypoints/cli/config/passphrase.py:152-154`).
- Existing profiles already carry envelopes with no recorded predecessor; the lineage rule applies to replacements from now on and must not make those envelopes unreadable.
- Localized operator text ships in all supported locales through the canonical catalogue.

## Implementation

Recovery reset is a forgotten-passphrase capability, not a compromise remedy, and the product says so. Every passphrase replacement, by current passphrase or by recovery code, re-wraps the same DEK through the one shared primitive and appends to the envelope lineage: the new envelope records the replaced envelope's self-digest as its predecessor and exactly the next generation, and the replace step refuses any other successor. Envelopes already stored without a predecessor remain readable; the rule governs what a replacement writes.

The replacement's audit event records which proof authorised it, current passphrase or recovery code, so a reset is distinguishable from a rotation in the profile's own history.

A failed recovery proof counts against the same per-profile attempt throttle as a failed login, and a throttled profile refuses a reset before any KDF work.

Sessions keep the existing fail-closed rule: an acceleration receipt minted before the replacement binds the old generation and is refused and removed at its next resume. That behaviour is proven by a test rather than extended.

The recovery record is untouched and the same code keeps working. The reset result and the command help state this, name `config profile recovery disable` then `enable` as the way to replace the code, and state that archives made before the reset still open with the passphrase they were made under. Archive restore itself is unchanged.

Each gap the reference lists becomes an implementation target: predecessor digest and generation enforcement at replace, the proof field on the replacement event, throttle participation, the operator text, and tests for pre-reset receipt refusal, restore of a pre-reset archive, the audit proof field, and lineage enforcement.

## Rationale

Holding the DEK epoch is what makes a reset cheap and safe for its real purpose, a lost passphrase: data, sentinel and recovery wrapper stay valid and nothing is re-encrypted (`2026-09-23-profile-password-custody-passphrase-reset-reference`). The same property means a reset cannot undo a compromise, so the honest boundary is to say that plainly instead of implying revocation. Recording the proof and chaining the envelopes turn an otherwise invisible credential change into auditable lineage without touching the unlock path, and throttling the proof closes the one online guessing surface the reset added.

## Consequences

An operator who forgot a passphrase regains the profile with an enrolled code, and the profile's history shows that recovery, not the old passphrase, authorised the change. An operator who suspects compromise learns from the product that a reset does not revoke older archives or the code, and that removing and re-enrolling recovery is the only rotation of the code available. DEK rotation stays the missing remedy for compromise; if it is ever accepted, a reset could offer to re-key, and this record would be superseded. Enforcing the lineage at replace means a replacement written by any future path must name its predecessor, which is the point.
