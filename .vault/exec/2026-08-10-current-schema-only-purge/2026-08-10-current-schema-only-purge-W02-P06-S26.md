---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a17cde9ccf3a86358208789f6c9fdd352ae8f77ab70fbaafcae76a45c5f467eb'
step_id: 'S26'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Make the master-key KDF preflight model require a real version

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`

## Description

- Require the version on the preflight preview model, removing the
  optional-and-defaulting-to-absent declaration.
- Keep the annotation loose on TYPE while making it strict on PRESENCE.
- Correct a refusal message in the reader that claimed a file was not a JSON
  object, which is false for an object that merely omits the marker.

## Outcome

Landed in `4641b8c`.

The model exists for one purpose: establish what format the key-derivation file
claims to be BEFORE strict parsing, so a foreign version produces a typed,
runbook-pointing error rather than a raw validation failure. It declared the very
version it exists to check as optional, defaulting to absent, so a file carrying
no version satisfied the preview and reached the comparison with an absence
standing in for a claim. A preflight that cannot fail on the one document it
exists to catch is not a preflight.

The presence-strict, type-loose split is deliberate. A file declaring a
non-integer version has something to name, and naming the offending value in a
typed error serves the operator better than a schema failure; absence has nothing
to name, so absence is the case the model itself refuses.

No legitimate file can refuse as a result. Both writers serialise the parameter
record with defaults included, so every file this build has written carries the
key. That was verified at the two write sites rather than assumed from the
field's declaration.

## Notes

This row exists because it was split OUT of the KDF parameter row rather than
taken as half of it. The parameter record's own markers cannot be required
without editing the mint and recovery writers, which is operator-held; this
preview model is read-only with a single call site and is never constructed by a
writer, so it is independent. Landing it under the other row's identifier would
have marked an owner-held row as delivered when only its unrestricted half had
shipped.

Owner-gated territory was not reached: no mint path, no key derivation, no
parameter record and no key schedule.
