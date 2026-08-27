---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:2949c75d8f46fac276a9246a800058e28bc081e98f183d42d8e43ce2a64a29ad'
step_id: 'S310'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the operations credential-free payload check type-aware so a content digest stops being refused for its name alone: the check matches forbidden tokens in a field name with no knowledge of the field's type, so an optimistic-concurrency content digest is refused while a hex-encoded secret under a benign name would pass, and the edit-contract request cannot be enrolled at all; admit a field only when it is BOTH typed as a content digest AND named with the digest token, keep every other name-matched field refused exactly as today, keep a field matching a second forbidden token refused even when digest-typed, and prove all three directions including a digest-typed field named for a secret

## Scope

- `the credential-free schema check and its forbidden-field-part set in application/operations/registry.py`
- `and a three-direction conformance test in the operations registry test module`

## Changes

- `M` `src/cadrumo/application/operations/registry.py`
- `M` `src/cadrumo/application/operations/tests/test_registry.py`
- `A` `.vault/adr/2026-08-27-tui-architecture-credential-free-type-aware-gate-adr.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_registry.py -m unit -n0` -> `pass`

## Notes

The Step row and the ADR title say "content digest" as a type-identity
test; the shipped check is a SHAPE test, and the ADR was amended before
acceptance to say so. `ContentDigest = Hex64Str` is a bare assignment
(`ContentDigest is Hex64Str` is `True`), and `Hex64Str` is deliberately
shared by `WorkUnitId`, `CalculationRevisionId`, `SnapshotId` and
`TransactionId` - there is no runtime way to test "declared as
`ContentDigest` specifically". The implemented rule instead admits a field
only when its JSON-schema fragment is Hex64-shaped (`minLength ==
maxLength == 64`, the lowercase-hex pattern) AND its name matches ONLY the
`digest` forbidden token; a field matching any other forbidden token stays
refused regardless of shape, and a field matching `digest` plus a second
token stays refused too. The residual risk this accepts - a Hex64-shaped
field declared for a sibling concept, named `*_digest`, is also admitted -
is stated in the ADR and pinned as its own conformance-test case rather
than left implicit.

Four directions proved, not three: admit (Hex64-shaped, digest-named);
refuse (plain-`str`, digest-named); refuse (Hex64-shaped, named for a
DIFFERENT forbidden token - `encryption_key`, the tripwire against the
exemption swallowing a hex-encoded secret); and admit (Hex64-shaped,
digest-named, but typed for a sibling concept - `WorkUnitId` - pinning the
accepted residual rather than leaving it to be discovered later. This is
also the first direct test coverage `_validate_credential_free_schema` has
ever had; no prior test exercised its name-refusal directly.

Unblocks `W05.P23.S144`.
