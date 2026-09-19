---
tags:
  - '#audit'
  - '#tui-architecture-w08-p27-s399-review'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:d8320856a1d0a493de6089ecd8e53fdc04e31c4e501b8b061f874a058bd02f64'
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

## Re-review disposition

The secret-HMAC remediation closes
`dictionary-recoverable-identity`: a random 256-bit module-private key is
generated once per process, is absent from the output object and its
JSON/repr/pickle forms, and makes the prior unkeyed dictionary result differ.
This contract is intentionally stable only for the running process, which is
the lifetime of refresh, reorder, resize, and child-return focus. S399 neither
needs nor now claims cross-process stability.

The projection validator now rejects missing and duplicated notification keys,
closing `optional-public-selection-key` for those two cases. The notification
row again has the exact seven safe fields and no action or operation fields,
closing `notification-action-regression`. Collision refusal, reorder
invariance, private-identity redaction, grammar/length, and module-secret
nonserialization were re-probed successfully.

### unconstrained-public-selection-key | high | Direct construction still accepts an arbitrary protected-looking NamespacedId as a public key

The selection-key alias is the general `NamespacedId` grammar rather than a
closed derived-key shape. Direct `AeatSyncWorkspaceProjectionV1.model_validate`
accepted `notification.private_identity` and serialized that value unchanged.
Thus the new validator proves only presence and uniqueness; it does not prove
that a public key came from the HMAC boundary or even has the
`aeat_sync.notification.k` plus 64 lowercase hexadecimal form. A caller can
still place a protected identity into object/JSON/repr/pickle through the
selection field.

### hmac-test-mapping | medium | The unkeyed-dictionary regression compares different identities depending on HMAC sort order

The test builds equal-date alpha and beta rows, takes the first row after
HMAC-key ordering, then compares that key with the unkeyed digest for alpha.
When beta sorts first, the assertion does not compare two derivations of the
same private identity. Use a single alpha fact or otherwise retain an
admission-side expected mapping for this assertion. Also reject arbitrary
namespaced keys that do not match the exact derived-key shape.

The remediation should define a constrained public selection-key type and
validate it both on the row and at the projection boundary. This is format
validation, not HMAC authentication: callers still cannot prove a key was
minted in this process, but they must be unable to serialize protected prose
or identifiers through the field. No cross-process test or persistence
contract is required.

Final re-review evidence: 14 focused application tests passed; Ruff passed; ty
passed; basedpyright reported zero errors, warnings, and notes. The separate
S379 public fixture builder still constructs notifications without a key and
will need to consume projected fixtures after S399 closes; that integration
work is not an additional S399 finding.

Final re-review result: **NO-CLOSE**.

## Final verification

The constrained selection-key type now admits only
`aeat_sync.notification.` followed by exactly 64 lowercase hexadecimal
characters. That constraint is enforced when constructing a notification row
and when validating a complete projection, closing the arbitrary
NamespacedId/protected-value escape. Focused adversarial cases reject a wrong
namespace, short digest, uppercase digest, and non-hexadecimal digest.

The HMAC regression now projects a single known private identity before
comparing its key with the former unkeyed content digest, so the assertion
proves the same-input distinction. The random module-private HMAC key remains
absent from projection object state and serialization, while rebuild/reorder
stability holds for the running-process lifetime required by refresh, resize,
and child return. No cross-process persistence behavior is claimed.

Missing and duplicate projection keys still fail, collisions still fail before
output, safe-key ordering remains input-order independent, protected identity
is absent from object/JSON/repr/pickle, and the notification DTO retains exactly
its seven closed non-action fields.

Final evidence: 18 focused application tests passed with all lanes enabled;
Ruff passed; ty passed; basedpyright reported zero errors, warnings, and notes.

Final result: **CLOSE**. S399 may close.
