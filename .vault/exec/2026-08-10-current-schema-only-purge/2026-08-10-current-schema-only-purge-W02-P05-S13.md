---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:1d71649f69311bdcb3a18c5ac8a818cf42c61345795167cb7e233364bcc0bcb2'
step_id: 'S13'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove encrypted-bundle marker refusal and current passphrase round trip

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export.py`

## Description

- Prove each of the three transport markers refuses when stripped from a real
  encrypted envelope.
- Prove the transport version refuses in BOTH directions, older and newer.
- Prove a current envelope still decrypts to the canonical cleartext bundle under
  a real passphrase.
- Assert all four markers are present on the serialized record.

## Outcome

Landed in `7ad5cc3` alongside the production change.

This file carried NO envelope refusal tests at all before this step. The
boundary's version fields were parsed, compared, and never once exercised against
a payload that violated them -- which is how three defaulted markers survived on
one record. The file is one of twelve integration modules that the default marker
lane does not select, so nothing had been watching it.

The strip-marker proofs are the anti-tautology work: a real bundle is encrypted
under a real passphrase, the marker is removed from the serialized envelope, and
the production decrypt path is asserted to refuse. Without the strip, every
refusal test could pass while the boundary silently re-defaulted.

The positive round trip is doing control duty rather than decoration: a suite of
refusals cannot distinguish a boundary that refuses the right things from one
that refuses everything.

## Notes

One case is unreachable through a file and is reached by direct construction
instead, disclosed in the test rather than quietly skipped: a PRE-CURRENT
transport version cannot be written to disk, because the current version is one
and the field's own lower bound is one, so no smaller legal value exists. The
older-direction refusal is therefore proven at the model boundary.

The record now carries zero defaultable fields, so strict equality across the
round trip covers its whole shape.
