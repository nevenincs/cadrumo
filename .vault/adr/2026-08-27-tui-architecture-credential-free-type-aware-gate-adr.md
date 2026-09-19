---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:830cb7031aabc5eaba1cffc9d3eaa9fbb0da48b31e93fa71aafbe2cdc1e2eb9c'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - '[[2026-08-11-tui-architecture-research]]'
---
# `tui-architecture` adr: `type-aware operation payload credential-free schema check` | (**status:** `accepted`)

## Problem Statement

The operations layer's credential-free payload check refuses any request
field whose NAME contains a forbidden token (`digest`, `hash`, `key`,
`secret`, `token`, `proof`, and similar), regardless of the field's type.
Enrolling the Modelo Edit Contract's compare-and-swap baseline as an
operation request surfaces four fields typed `ContentDigest` -
`permitted_surface_digest`, `completeness_manifest_digest`,
`contract_set_digest`, `definition_contract_digest` - each a SHA-based
content hash of catalogue or schema state, used only for optimistic-
concurrency comparison. None of them is secret material. The check refuses
all four purely because their names contain `digest`, blocking a
`CREDENTIAL_FREE_JOURNAL` request that otherwise has no other objection.

A decision is needed now because no field-renaming or storage-policy
workaround is acceptable (see Considered options), so the enrollment cannot
proceed until the check itself is corrected.

## Considerations

- What the two request-storage policies actually do:
  `OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL` journals the
  validated request as plain JSON; `SECURE_REFERENCE` routes it through the
  encrypted operand store (`supervisor.py`, `submit()`, the
  `request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE` branch
  versus its `else`).
- `ModeloWorkAmendRequest` already ships under `CREDENTIAL_FREE_JOURNAL` and
  carries a real filing-grade financial correction amount
  (`ModeloWorkAmendOverride.value`, an exact decimal string). Its own
  docstring independently documents the same Decimal validation-versus-
  serialization asymmetry this enrollment also hit, and fixes it the same
  way (a string-only value). A request carrying real casilla financial
  values already journals in the clear today, accepted and shipped.
- `ContentDigest` is a closed, narrowly-shaped type (a fixed-length hex
  digest string) with no representational capacity for a bearer token or a
  passphrase - a value of this SHAPE cannot carry most of what the check
  exists to keep out of a clear-text journal.
- `ContentDigest = Hex64Str` (`core/identity/_digest.py`) - a bare
  assignment, not a distinct type. Confirmed by inspection:
  `ContentDigest is Hex64Str` is `True`, and pydantic's own field
  introspection (`model_fields[name].annotation`) resolves a
  `ContentDigest`-declared field to plain `str`, with the `Annotated[...]`
  wrapper already stripped. `Hex64Str` is deliberately the SHARED shape
  primitive for many unrelated concepts - `WorkUnitId`,
  `CalculationRevisionId`, `SnapshotId` and `TransactionId` are all also
  `= Hex64Str` (`core/_hex.py`, which explicitly instructs against minting a
  new per-concept alias). So there is no runtime test for "declared as
  `ContentDigest` specifically" - only for "shaped like Hex64Str", which
  every one of those sibling concepts shares.
- The check's own purpose is to keep secret-shaped VALUES out of a clear
  journal. A name heuristic is a proxy for that; a SHAPE check on a field
  provably incapable of holding a bearer-token- or passphrase-shaped value
  is a more precise proxy for the same purpose, though not as precise as a
  true type-identity check would have been had one been available.

## Considered options

- **Shape-AND-name exemption for Hex64-shaped, digest-named fields
  (chosen).** `ContentDigest = Hex64Str`, a 64-character lowercase hex
  string, and that shape is shared verbatim by `WorkUnitId`,
  `CalculationRevisionId`, `SnapshotId` and `TransactionId` - there is no
  runtime way to test "declared as `ContentDigest`" specifically (see
  Considerations), so the achievable check is a SHAPE test, not a type-
  identity test. A 256-bit secret (an AES-256 key, a raw HMAC key, a derived
  DEK) is exactly 32 bytes, which hex-encodes to exactly 64 characters -
  indistinguishable from a SHA-256 digest by shape alone. Admitting every
  Hex64-shaped field regardless of name would therefore admit
  `encryption_key: ContentDigest`, a real loosening of the guarantee in
  exactly the case the check exists to catch. The check instead requires
  BOTH conditions together: the field's declared shape is Hex64 AND its
  name matches the existing digest-shaped name pattern, and no OTHER
  forbidden token. A field failing either condition keeps today's exact
  outcome - refused if name-matched, and the shape test changes nothing for
  a field the name check does not already flag.
- **Rename the wire fields away from `digest` (rejected).** Defeats the
  heuristic for every future field with that name, including a genuine
  secret smuggled under a hash-shaped name - the exact case the check
  exists to catch. Resolves a red gate by hiding the construct from the
  matcher rather than correcting the matcher.
- **Adopt `SECURE_REFERENCE` for this request (rejected).** Routes a
  filing-grade request into encrypted storage for a reason unrelated to
  storage - because the check happened to skip it - rather than because the
  request needs confidentiality. No existing modelo operation uses this
  policy; adopting it here would establish the pattern for the wrong reason.
  An "interim" label does not change that the choice would be wrong, only
  that it says so.
- **Drop the digest fields from the operation's request payload (rejected).**
  All four fields are non-optional on the real domain baseline type
  (`ModeloEditBaselineV1` and its nested `ModeloEditSchemaIdentityV1` /
  `ModeloEditCompatibilityTupleV1`), so omitting them from the wire mirror
  would leave nothing to reconstruct them from at translation time except a
  fabricated placeholder value.
- **Mint a distinct, runtime-distinguishable `ContentDigest` marker
  (available, not chosen now).** A `NewType`, subclass, or schema-level
  marker would let the check test true type identity instead of shape,
  closing the residual risk below completely. Its real cost: it touches
  `ContentDigest`'s declaration site and potentially every consumer across
  the codebase, and `core/_hex.py` actively instructs against minting new
  per-concept aliases over the shared `Hex64Str` primitive - so adopting it
  would reverse that guidance and needs its own decision, not a rider on
  this one. Recorded here as the escalation path if the residual risk below
  is ever judged unacceptable.

## Residual risk

What the check now guarantees: a field is admitted only when its declared
shape is exactly Hex64 (64 lowercase hex characters, matching
`Hex64Str`/`ContentDigest`'s constraint) AND its name matches only the
`digest` token among the forbidden set. What it does NOT guarantee: that the
field was declared specifically as `ContentDigest` rather than one of its
shape-sharing siblings (`WorkUnitId`, `CalculationRevisionId`, `SnapshotId`,
`TransactionId`), and that a Hex64-shaped field named `*_digest` cannot, in
principle, hold a 256-bit secret hex-encoded to the same width.

The gap is tolerated because exploiting it requires DELIBERATE misuse, not
an easy mistake: someone would have to name a real key or secret field
`*_digest` specifically, constrain it to exactly 64 hex characters, and
avoid every other forbidden token (`key`, `secret`, `auth`, and the rest
still bite on any of those). A field genuinely meant to carry key material
is overwhelmingly more likely to be named for what it is, and the existing
name check continues to refuse it the moment it is. If this residual is
ever judged unacceptable, the escalation path is the distinct-marker option
above, not a further loosening of the shape test.

## Constraints

- The fix lives in the operations registry's request-storage validator
  (`registry.py`'s `_validate_credential_free_schema`, distinct from the
  STRUCTURAL model-graph check in `_model_contract.py`'s
  `require_strict_frozen_operation_model_graph` - same call chain, via
  `_strict_model_json_schema`, but a different concern: one refuses lax
  model shapes, the other refuses secret-shaped field names), consumed by
  every registered operation definition across the codebase. The boundary
  that must not move: a field is admitted ONLY when it is BOTH Hex64-shaped
  AND name-matched as digest-shaped and no other forbidden token; a field
  that is name-matched but NOT Hex64-shaped (a bare unconstrained `str`
  named `*_digest`) is refused exactly as before; a field that is
  Hex64-shaped but not name-matched is unaffected because the name check
  never flagged it; and a field matching `digest` AND a second forbidden
  token (`session_key_digest`) is refused regardless of shape. No admission
  decision may rest on shape alone.
- No frontier or unstable dependency; this is a pure typing/introspection
  change to an existing, already-shipped validator.

## Implementation

Extend the schema-walk that backs `_validate_credential_free_schema` to
carry each field's JSON-schema SHAPE (its `pattern`, `minLength` and
`maxLength`, already present in the schema fragment being walked - no
separate pass over the Pydantic field graph is needed) alongside its name.
The `digest` name token is split out of the general forbidden-parts set into
its own narrower rule: a field whose name matches ONLY the `digest` token
(and no OTHER forbidden token) is admitted when its schema shape is exactly
Hex64 (`minLength == maxLength == 64` and the lowercase-hex pattern), and
refused otherwise exactly as today. A field matching ANY other forbidden
token - `secret`, `key`, `auth`, `password`, and the rest - is refused
regardless of shape and regardless of whether it also matches `digest`; the
exemption never widens any token but `digest`, and never overrides a second,
independently-matched forbidden token on the same field. A conformance test
proves all four directions: a Hex64-shaped field named `*_digest` is
admitted; a plain-`str` field named `*_digest` is still refused; a
Hex64-shaped field named for a DIFFERENT forbidden token
(`encryption_key: ContentDigest`) is still refused; and a Hex64-shaped field
typed for a DIFFERENT Hex64-shaped concept (`WorkUnitId`) but still named
`*_digest` is ADMITTED - documenting, rather than silently permitting, the
residual risk this ADR accepts.

## Rationale

The check's purpose - keep secret-shaped values out of a clear-text journal
- is served better, though not perfectly, by admitting a field whose SHAPE
rules out most of what the check exists to catch. A true type-identity test
was considered but is not achievable without minting a distinct marker
(see Considered options), which is a bigger, separately-decided change; the
shape test is the strongest guarantee available without it, and its
residual risk is named and bounded above rather than left implicit. The
alternative options either sacrifice the check's own integrity for every
future caller (renaming), make a storage decision for a reason disconnected
from storage risk (`SECURE_REFERENCE`), or require fabricating data that
does not exist (dropping the fields). The shape-aware check is a strict
narrowing of the false-positive population this defect describes, accepting
one named, bounded residual in exchange.

## Consequences

- Unblocks the Modelo Edit Contract's operation enrollment (and any future
  enrollment) from having to choose between a forbidden workaround and an
  incorrect storage policy whenever a compare-and-swap coordinate happens to
  be named for what it is.
- The shared gate gains one more shape-aware exemption, precedent for
  extending the same treatment to other provably-non-secret-shaped fields in
  future, should one surface the same false positive - each such extension
  should be its own reviewed change, not a blanket carve-out.
- Requires a conformance test asserting the boundary does not move, in four
  directions: a Hex64-shaped, digest-named field is admitted; a plain-`str`
  digest-named field stays refused; a Hex64-shaped field matching a
  DIFFERENT forbidden token (`encryption_key`) stays refused - the tripwire
  against the exemption swallowing a hex-encoded secret sharing
  `ContentDigest`'s shape; and a Hex64-shaped field typed for a sibling
  concept (`WorkUnitId`) but named `*_digest` is admitted - the residual
  risk this ADR accepts, pinned as a test rather than left to be discovered
  later.
- This is also the first direct test coverage `_validate_credential_free_schema`
  has ever had: no existing test exercised its name-refusal directly before
  this change, so a credential-leak guard on a filing-grade journal had been
  defended only incidentally, by operation definitions that happened to
  satisfy it.
