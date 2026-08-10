---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6fc24b7af3b06d6caa17de5324801ee86d0d969e07667fa4f3a4a57e7d212a91'
step_id: 'S10'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require and preflight the exact current WrappedMasterKey marker before decryption

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`

## Description

- Declare a named constant for the wrapped recovery master key's format version.
- Drop the default from the record's version field so the marker is required.
- Stamp the version explicitly when the record is built from stored bytes.
- Compare the claimed version as the FIRST statement of the unwrap, ahead of the
  length gate, the recovery-key read and the KEK derivation.
- Export the constant from the module's public surface.

## Outcome

Landed in `82db6a7` with its proof step.

The field carried a default of one, no exactness check existed anywhere, and
nothing was consulted before the unwrap ran. A marker parsed into a field and
then read by nobody is not a compatibility mechanism.

Ordering carries more weight on this boundary than on the others. This file is
the last route back to a bucket whose master key is otherwise lost, so feeding a
format this build cannot interpret into a decryption produces either garbage or
an authentication failure that misdirects the operator into believing their
recovery phrase is wrong. The check sits ahead of the recovery key entirely, not
merely ahead of the decrypt call, because deriving the KEK already spends the
operator's recovery material and a refusal arriving afterwards has done the thing
it exists to prevent.

The version field stayed a plain integer with an explicit gate rather than
becoming a pinned literal. A literal would move the mismatch into the parser and
leave the preflight as dead code, which on this particular boundary trades a
loud, well-worded refusal for a raw validation error at the least useful moment.
The opposite choice was correct for the pointer document, where nothing needed to
read the version before the model existed.

## Notes

Owner-gated territory was NOT reached: no key schedule, no data-encryption-key
derivation and no mint path was touched. The record is also not enrolled in the
durability or upgrader machinery, so no forward-only control was disturbed.
