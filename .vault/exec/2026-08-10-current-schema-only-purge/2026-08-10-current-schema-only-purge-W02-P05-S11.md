---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:da1e41d72c6375f0ddd213067e7c3cc8f9e8c5135e6fc94eb7240c2b110e22d5'
step_id: 'S11'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove wrapped-master-key marker refusal precedes real unwrap

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`

## Description

- Prove a non-current version refuses before the unwrap runs.
- Prove a stored file with the version line removed surfaces the refusal at read.
- Add discriminators establishing that the refusal precedes the recovery-key read
  and the key derivation, not merely the decrypt call.
- Correct a constructor in the existing suite that omitted the now-required
  marker.

## Outcome

Landed in `82db6a7` alongside the production change. Added to the existing
wrap-and-unwrap classes rather than starting a parallel structure, since this
file is class-based unlike the others this campaign has touched.

The ordering discriminators are the substance. Asserting only that a bad version
raises would pass equally against an implementation that derived the key first
and refused afterwards, which is the failure being closed. The discriminators are
mock-free: the question is whether the recovery material was reached, and a
stand-in for the thing whose use is under test cannot answer that.

## Notes

Both records this phase touched now carry no defaultable fields at all, so strict
equality across the round trip covers the whole shape rather than the subset a
fixture happened to populate.

One nested field still defaults, disclosed rather than papered over: the
authenticated-encryption algorithm. Its catalogue has exactly one member, so no
non-default value exists to populate it with. Recording that is more useful than
claiming full non-default coverage, because the next reader can tell the
difference between a gap and an impossibility.
