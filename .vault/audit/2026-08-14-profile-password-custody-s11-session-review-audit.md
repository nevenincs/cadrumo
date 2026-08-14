---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e9da4e973736745cf7866e36e26f5763540749a2777795e64f484efa27f61072'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `s11 session review`

## Scope

Independent review of `W02.P04.S11` against the accepted profile-custody
session contract. The review covered random session-key generation, UUID-pair
keychain accounts, authenticated receipt metadata, current-envelope validation,
keychain-unavailable behavior, narrow revocation, repeated mint, filesystem
safety, real tests, static evidence, and the stated external blockers. S12 and
production remediation were excluded.

## Findings

The cryptographic core is coherent. Mint generates a random 32-byte session
key and random session UUID; the keychain account is the immutable profile UUID
plus session UUID. AES-GCM AAD binds schema, profile, session, custody
generation, DEK epoch, issued instant, idle deadline, and absolute deadline.
Application resume loads the current committed password envelope before asking
the adapter to unwrap. The implementation has no runtime provider, shared
master-key, global account, or fallback-key API. A call-time keychain failure is
normalized to typed process scope without publishing a disk-only receipt.

### s11-session-receipt-bypasses-custody-filesystem | resolved | Receipt filesystem authority is bounded and anchored

`resume_profile_session` first calls `Path.is_file()`, then separately performs
`Path.read_text()` with no byte ceiling or no-follow handle. `delete_profile_session`
uses the same unbounded path read, and refusal cleanup calls `Path.unlink()`
after separately parsed bytes. The JSON parser accepts alternate whitespace and
duplicate-member encodings rather than requiring one canonical receipt. A link
or reparse leaf, oversized file, or sibling replacement can therefore cross the
established anchored local-record boundary and can make cleanup act on a leaf
other than the one evaluated. Session acceleration is cache-only, but it carries
the authority that selects an OS-keychain account and unwraps a DEK, so this is
an integrity boundary rather than harmless formatting debt.

Remediation verified: receipt and retirement records now use bounded exact-
canonical custody reads and captured-byte CAS mutation. Hostile oversized,
duplicate, noncanonical, link/reparse, nonregular, and substitution artifacts
refuse without opening or deleting redirected targets.

### s11-remint-orphans-prior-session-key | resolved | Ordered swap owns the displaced UUID key

`mint_profile_session` creates and verifies a new keychain secret, then
atomically overwrites `session.v2.json`, but it never reads and retires the
previous receipt's exact profile/session account after publication. The real
two-mint test confirms this behavior by finding both keychain entries and
manually deleting the first one in test cleanup. The old secret is no longer
usable without the displaced receipt, but it remains an unowned durable secret
and violates the required atomic reference swap and ordered retirement. A
failure-aware rotation must keep the previous receipt/account recoverable until
the new pair is durable, then revoke exactly the displaced account without
global enumeration.

Remediation verified: mint captures the exact prior receipt, journals exact
predecessor/successor bytes, stores and verifies the new pair, and retires only
the displaced UUID-pair account after publication.

### s11-retirement-delete-is-not-idempotent | resolved | Exact-account retirement converges idempotently

`_recover_pending_retirement` blindly deletes the successor account when the
current receipt is the predecessor, and the predecessor account when the
current receipt is the successor. A process can die after publishing the
pending record but before storing the successor key, or after deleting the
displaced key but before clearing the pending record. On retry, common keyring
backends raise `PasswordDeleteError` for that already-absent account.
`_delete_acceleration_secret` normalizes it to `KeyringUnavailableError`, so the
journal remains and the same delete fails forever. Absence on a usable backend
is successful retirement, not backend unavailability; both crash boundaries
must converge idempotently.

Remediation verified: retirement reads the exact UUID-pair account first. A
usable backend reporting absence succeeds; an unavailable backend retains the
journal; a present account is deleted and reread to prove absence.
`PasswordDeleteError` triggers the same exact reread. Both pending branches use
this operation.

Focused AAD and receipt tests passed, including 16 non-keychain cases in 11.66
seconds, without
fakes, mocks, stubs, patches, skips, or expected failures. The reported adapter,
non-keychain, taxonomy, precondition, and static gates are consistent with the
inspected code. The live WinVault `WinError 1312` proves only the typed
unavailable path and is not counted as successful persistence. The stale MCP
schema inventory is external. The fresh-process crash tests truthfully prove
WinVault-unavailable evidence preservation on this host, not usable-keychain
success. Verdict is **PASS** with no CRITICAL or HIGH finding.

## Recommendations

Route session receipt create/read/replace/clear exclusively through the bounded,
anchored, no-follow custody local-record authority on POSIX and Windows. Define
a small explicit limit, exact canonical JSON with duplicate-key refusal, and
captured-byte/identity compare-and-clear cleanup. Add real oversized,
noncanonical, link/reparse, and sibling-substitution tests.

Implement mint as a journalled or equivalent recoverable swap: capture the
exact prior canonical receipt, publish and verify the new key plus receipt, then
delete only the displaced UUID-pair account. On any pre-publication failure,
remove only the new key and retain the old pair; on post-publication retirement
failure, retain a bounded receipt that deterministically finishes retirement.
Add real repeated-mint success and keychain/disk failure-boundary tests proving
one current account, no orphan, and exact rollback or roll-forward ownership.

Make UUID-pair revocation idempotent while preserving unavailable evidence:
read the exact account first; a usable backend reporting absence is successful
retirement, while an unavailable backend retains the journal. If present,
delete and verify absence. Add real subprocess recovery cases for death before
successor storage and after predecessor deletion but before journal clear.

Proceed to S12 without weakening exact-account ownership, unavailable evidence
preservation, or bounded receipt recovery.
