---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:44a4559d655a5ccfe6ebc9487cfffe2d1aa200f9e3f850432b1d93fdff68cdc4'
step_id: 'S45'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Integrate the S46 producer snapshot as the sole closed public producer vocabulary and payload-axis authority

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/user_profile/`
- `src/cadrumo/domain/user_profile/`
- `src/cadrumo/core/`
- `dev/registry/`
- `src/cadrumo/_data/registry/aeat/modelos/`

## Description

- Replace raw export header keys with the closed dotted `FilingProducerKey` vocabulary at the strict TOML loader boundary.
- Route renderer and composer inputs through one immutable typed filing producer snapshot.
- Move Renta declaration modality to its sole core type and persisted `renta_filing.declaration_type` home.
- Delete profile `export_headers`, every export-only `filing_export.*` account path, compatibility aliases, raw dictionaries, selector copies, and fallbacks.
- Withdraw incomplete fixed-width layouts atomically, remove their casilla export references, and ground each withdrawal in an explicit decision and construct membership.
- Preserve admitted complete layouts and migrate their producer tokens without historical aliases.
- Prove charge and refund account isolation through a fresh test-owned layout loaded by the real registry loader and rendered by the public typed snapshot path.
- Replace obsolete legacy-positive tests with strict refusal, canonical vocabulary, withdrawal, codec, and emitted-wire gates.

## Outcome

The public producer boundary is closed and typed. Registry `header_key` declarations, production `export_headers`, and production `filing_export.*` paths have zero matches. Unsupported layouts are absent by explicit grounded decision rather than partial rendering. The isolated Modelo 303 DID authority proves exact 823-byte Latin-1 output, charge/refund field isolation, missing-account refusal before emission, and continued refusal of production Modelo 303 export support.

Validation completed with the development registry lane at 107 passing tests, the final focused review lane at 109 passing tests, the thirteen reconciled registry tests passing, the five emitted-wire tests passing, Ruff clean, BasedPyright at zero diagnostics, and an independent Luna review at critical zero, high zero, medium zero.

## Notes

Twenty-six obsolete legacy test modules were deleted: eighteen filing tests, seven modelo tests, and one user-profile persistence test. Three unrelated deleted tests in the shared tree are outside this step and excluded from delivery. The production Modelo 303 layout remains withdrawn; the test-owned layout proves the producer-to-wire contract without advertising or reviving production support.
