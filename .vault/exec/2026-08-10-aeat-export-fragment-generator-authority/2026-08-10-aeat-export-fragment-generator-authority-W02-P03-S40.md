---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:87c847b5558de1317a28efb7f8b2b6ce70f1b0691684fcd8cd91bbaaa0079e0f'
step_id: 'S40'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Add a canonical exact allowed-values constraint for reviewed fixed-width integer enumerations to the export schema and sole registry codec, reject incompatible or noncanonical domains, enforce render and parse symmetrically, and carry the constraint through loader-semantic provenance without a second value-policy taxonomy

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`

## Description

- Add one optional immutable exact allowed-values domain to `ExportFieldDefinition`.
- Canonicalise the domain as an order-independent set and refuse empty, duplicate, non-ASCII, noncanonical, out-of-width, incompatible, or value-policy-overlapping declarations.
- Enforce the same semantic domain through the sole fixed-width codec on both render and parse after canonical numeric normalization.
- Advance loader-semantic normalization and include the exact domain in its canonical digest.
- Add real positive, refusal, ordering, mutation, and single-owner structural tests.

## Outcome

The export schema now represents reviewed fixed-width integer enumeration domains without creating another value-policy taxonomy. Author order is canonicalised, semantic values are checked before rendering and after parsing, and padded wire spellings resolve to the same exact domain member. A field cannot combine this constraint with a value policy, so the S37 checkbox and short-year contracts remain sole authorities for their values.

Focused codec, schema, parser, and value-policy verification passed with 116 tests; the broader registry-schema slice passed with 143 tests. The final remediation slice passed 47 tests. Ruff passed and strict BasedPyright reported zero diagnostics. Independent formal review closed its one HIGH finding after coexistence refusal and order-invariance remediation; no open high, medium, or low findings remain.

The schema, codec, tests, audit, and initial execution record landed in `fd804c8a10`. The isolated loader-semantic version, normalization, and digest-mutation follow-up landed in `6f89cfc80e`; its cached diff contained exactly the two reviewed development-tool files and excluded every paused S32 profile/provenance change.

## Notes

The independent reviewer reran Ruff and strict BasedPyright after remediation. Three post-remediation reviewer pytest attempts could not collect during transient peer edits to registry identifier/protocol modules; the durable audit separates that boundary from the executor's green post-remediation lane. No S40 test failed. Paused S32 render-profile and provenance-schema work remains uncommitted and is excluded from this Step's commits.
