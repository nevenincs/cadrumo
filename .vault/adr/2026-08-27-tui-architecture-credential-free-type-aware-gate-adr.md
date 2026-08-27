---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:1bb19d519a99eaf64943a378560de105ed865dd9559d542e5a84b04a49a36d47'
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

## Constraints

- The fix lives in the shared operations contract module
  (`_model_contract.py` / `registry.py`'s `_validate_credential_free_schema`),
  consumed by every registered operation definition across the codebase.
  The boundary that must not move: a field is admitted ONLY when it is BOTH
  typed `ContentDigest` AND name-matched as digest-shaped; a field that is
  name-matched but NOT `ContentDigest`-typed (`encryption_key: ContentDigest`
  included, since its name does not match the digest pattern) is refused
  exactly as before, and a field that is `ContentDigest`-typed but not
  name-matched is unaffected because the name check never flagged it. No
  admission decision may rest on type alone.
- No frontier or unstable dependency; this is a pure typing/introspection
  change to an existing, already-shipped validator.

## Implementation

Extend the schema-walk that backs `_validate_credential_free_schema` (or the
call site that invokes it from `_strict_model_json_schema`) to carry the
originating Pydantic field's annotated type alongside its JSON-schema
fragment, rather than walking a bare JSON-schema dict with no type context.
The `digest` name token is split out of the general forbidden-parts set into
its own narrower rule: a field whose name matches ONLY the `digest` token
(and no OTHER forbidden token) is admitted when its declared type is exactly
`ContentDigest` (or a `ContentDigest`-typed optional/tuple thereof), and
refused otherwise exactly as today. A field matching ANY other forbidden
token - `secret`, `key`, `auth`, `password`, and the rest - is refused
regardless of type and regardless of whether it also matches `digest`; the
exemption never widens any token but `digest`, and never overrides a second,
independently-matched forbidden token on the same field. A conformance test
proves all three directions: a `ContentDigest`-typed field named `*_digest`
is admitted; a plain-`str` field named `*_digest` is still refused; and a
`ContentDigest`-typed field named for a DIFFERENT forbidden token
(`encryption_key: ContentDigest`) is still refused.

## Rationale

The check's purpose - keep secret-shaped values out of a clear-text journal
- is served exactly as well, and more precisely, by admitting a field whose
TYPE proves it cannot hold a secret. The alternative options either
sacrifice the check's own integrity for every future caller (renaming),
make a storage decision for a reason disconnected from storage risk
(`SECURE_REFERENCE`), or require fabricating data that does not exist
(dropping the fields). The type-aware check is a strict narrowing: it
removes exactly the population of false positives this defect describes and
touches no other case.

## Consequences

- Unblocks the Modelo Edit Contract's operation enrollment (and any future
  enrollment) from having to choose between a forbidden workaround and an
  incorrect storage policy whenever a compare-and-swap coordinate happens to
  be named for what it is.
- The shared gate gains one more type-aware exemption, precedent for
  extending the same treatment to other provably-non-secret domain types in
  future, should one surface the same false positive - each such extension
  should be its own reviewed change, not a blanket carve-out.
- Requires a conformance test asserting the boundary does not move: a
  `ContentDigest`-typed, digest-named field is admitted; a plain-`str`
  digest-named field stays refused; and a `ContentDigest`-typed field
  matching a DIFFERENT forbidden token (`encryption_key`) stays refused -
  the explicit tripwire against the exemption swallowing a hex-encoded
  secret that happens to share `ContentDigest`'s 64-character shape.
