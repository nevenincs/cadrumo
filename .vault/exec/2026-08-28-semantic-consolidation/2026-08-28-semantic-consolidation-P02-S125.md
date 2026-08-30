---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:35c06d167fe051450d3a47b0f2af67acf3982dbbd9fabe1d2db5b8eb001c02fc'
step_id: 'S125'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the represented-NIF length bound once and the two password-generation bounds beside the envelope that owns them, closing a result payload that reported a generation the envelope would refuse to store

## Scope

- `src/cadrumo/application/auth/`
- `src/cadrumo/adapters/persistence/storage/custody/`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/application/auth/apoderado_service.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/records.py`
- `M` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `verify:` `pytest src/cadrumo/adapters/persistence/storage/custody -n 0` -> `pass` (245)
- `verify:` `pytest src/cadrumo/application/auth -n 0 -m ""` -> `pass` (375; one pre-existing extra_forbidden failure)

## Notes

The obvious consolidation for `represented_nif` was to adopt the canonical
`SubjectTaxId` alias. Checking first showed why that would have been wrong: the
apoderamiento flow validates that field through `validate_identity`, the
``_documents`` implementation, while `SubjectTaxId` runs `validate_spanish_tax_id`,
the ``_tax_id`` one. Those two disagree about the ABEH CIF leader class, so the
adoption would have moved a live field from one policy to the opposite without
anyone deciding to. Only the uncontested LENGTH bound was consolidated, and the
CIF audit now records that the divergence sits on a live path rather than merely
inside one package.

`password_generation` was not simply restated. The result payload declared
``ge=2`` and NO ceiling, while the custody envelope declares ``ge=1`` and a
maximum -- so neither bound was a superset, and the payload could report a
generation the envelope would refuse to store. Both are now declared beside the
envelope: the general counter, and the narrower post-change form whose lower
bound is genuinely two because a profile starts at one. Probed rather than
restated: two accepts, one refuses as pre-change, and a value above the custody
ceiling refuses.
