---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:e5731a8b8214dfd253226b52afa91914989522343ca28c6fbe1e8c1eaee85b60'
step_id: 'S138'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# replace raw source-object identity with the exact persisted source reference across connected proof

## Scope

- `src/cadrumo/core`

## Description

- Replace the raw source-object field with the exact persisted `source_ref` identity.
- Join encrypted-proof identity byte-for-byte to the connection source reference.
- Exercise namespaced invoice and foreign-asset source-reference shapes.
- Refuse raw, normalized, or differently namespaced substitutions.

## Outcome

Connected proof now names the same resolver-authored source reference persisted
on `CalculationSourceRef`. The contract requires exact identity and leaves no
prefix stripping, normalization, alias, or legacy object-id path for the live
authority to interpret.

## Notes

Resolver ownership remains an independent live-enrollment decision because the
encrypted calculation provenance deliberately does not persist `resolver_id`.
