---
tags:
  - '#audit'
  - '#tui-architecture-w08-p27-s399-review'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e609d32a9bd351d1451070f8c842a6773549d5dc3f173078ab21ffd9dff646e1'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture-w08-p27-s399-review` audit: `AEAT Sync notification selection identity review`

## Scope

Reviewed the live S399 notification-selection implementation and focused tests
against the exact plan row, the closed S397 projection contract, identifier
grammar, redaction/storage rules, and application boundary. The review
exercised direct public-model construction, deterministic rebuild/reorder,
collision refusal, serialization, and low-entropy offline dictionary recovery.

## Findings

### dictionary-recoverable-identity | high | Domain-separated SHA-256 does not make a guessable private identity non-recoverable

`_notification_selection_key` hashes a public namespace and the private
identity with the unkeyed canonical content-hash function. Domain separation
and cross-process determinism are sound, but anyone holding an output key can
hash candidate identities and compare them offline. The review reproduced
exact keys for low-entropy guesses. A stable non-secret HMAC key has the same
weakness; HMAC supplies secrecy here only when its key is secret.

### optional-public-selection-key | high | Direct public projection construction admits a notification with no selection identity

`AeatSyncWorkspaceNotificationRowV1.selection_key` is optional because one
type is used before and after projection, while the projection validates only
the zone catalogue. Direct `model_validate` accepted a public projection with
a notification whose key was `None`. The projector normally fills it, but its
procedure is not a public contract invariant.

### notification-action-regression | high | S399 reopens action authority on the closed S397 notification row

The notification row inherits `AeatSyncWorkspaceActionRowV1`, serializes
supported actions and operations, and tests require that state to survive.
S397 restricted action-bearing public output to overview, evidence comparison,
and reconciliation. Selection identity work does not authorize another action
surface.

### selection-test-teeth | medium | Tests omit the direct-construction, dictionary, and closed-field escapes

Tests prove reorder stability, bounded grammar, literal non-retention,
collision refusal, and same-process determinism. They do not try a `None` key
in a directly constructed projection, recover a guessed private identity, or
pin the notification row's closed field set.

## Recommendations

S399 must not close in its current form.

1. Separate admission and public notification types, or add a projection
   invariant requiring a validated key on every public notification.
2. Use an injected securely stored stable secret pepper with defined
   version/rotation behavior, or consume a source-issued high-entropy opaque
   identity. A public/non-secret HMAC key is not a remedy. Injection preserves
   projector purity; the projector must perform no I/O.
3. Restore the S397 notification row's non-action field set.
4. Add direct-construction, low-entropy dictionary, closed-field-set, and
   independent-process stability tests.

Verified strengths: the current key is domain-separated, deterministic,
within `NamespacedId` grammar and length, used for safe ordering, and collision
checked. Private identity is absent from output object/JSON/repr/pickle, and no
I/O, adapter, TUI, or new execution dependency was introduced.

Focused evidence: 14 tests passed; Ruff passed; ty passed; basedpyright reported
zero errors, warnings, and notes. Final result: **NO-CLOSE**.
