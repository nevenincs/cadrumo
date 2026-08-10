---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:4bc3c15c7b23b7395a1e0c6869294b17cf5957ee6f0aaff3c56b92ca7c486914'
step_id: 'S09'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove CipherEnvelope marker refusal occurs before master-key access

## Scope

- `src/cadrumo/adapters/persistence/storage/envelope/tests/test_cipher_envelope_version_gate.py`

## Description

- Prove a stored envelope OMITTING the version marker refuses.
- Prove that refusal, like the mismatch refusal, happens before the master key is
  consulted.
- Keep the existing future-version and ordering coverage intact.

## Outcome

Landed in `44ead4e` alongside the production change.

The file already proved a future version refuses and that the mismatch refusal
precedes master-key access. It did not cover omission at all, which was exactly
the case the field's default made unreachable.

The two refusals now arrive by different routes and both are proven ahead of key
access: omission is refused at parse, because the field is required, while a
mismatch is refused at the explicit gate. Proving the ordering for the mismatch
case said nothing about the omission case, since they do not share a code path.

Ordering is established with a key provider that trips if consulted, not with a
mock -- the discriminator is whether the key was reached, so the test has to be
able to observe reaching it without standing in for it.

## Notes

A refusal that fires after key derivation has already spent the secret it exists
to protect, which is why ordering is asserted rather than assumed from reading
the source.
