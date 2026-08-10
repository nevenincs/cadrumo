---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:670de7b0cf40b14523f1dc78735145c713823ebc637ed68319c10e5dc66d105e'
step_id: 'S41'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Promote every reviewed singleton numeric value-policy token to the canonical public export policy axis and enforce exact integer, implied-decimal, date, enumeration, digit-string, identifier, four-digit-year, month, and day semantics through the sole fixed-width codec, deleting the development-only literal taxonomy and refusing silent generic mappings

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`

## Description

- Promote the complete reviewed singleton token set into the public closed `ExportValuePolicy` enum and add one public required coercing value type.
- Delete the development-only `SingletonValuePolicy` literal union and consume the public required policy type in strict render-profile TOML.
- Validate each policy against its exact field shape and require `ENUMERATED_DIGITS` whenever `allowed_values` is declared.
- Enforce strict semantic projection and canonical wire validation for unsigned integers, implied decimals, calendar dates, enumerations, digit identities, identifiers, full years, months, and days.
- Preserve non-invertible short-year parse state through an explicit policy-bound parsed-wire value while retaining the four-digit semantic input requirement.
- Make the singleton generator mapper exhaustive across all public policy members and refuse unknown policy shapes.
- Move the stale development semantic-map `CasillaId` import to its canonical core owner after the registry forwarding alias was intentionally removed.
- Add real schema, codec, parser, strict TOML, all-policy roundtrip, enumeration-domain, and all-policy mapper tests.

## Outcome

The public registry domain now owns all eleven reviewed singleton policies. Every policy is projected and wire-validated by the canonical policy and fixed-width codec path, and render to parse to render is exact for every member. Digit strings and identifiers retain leading-zero identity, calendar policies reject impossible dates and ranges, unsigned numeric policies reject lossy or signed values, and enumeration domains have one representation: `ENUMERATED_DIGITS` plus canonical semantic `allowed_values`.

The selected final executor lane passed 290 tests. The independent reviewer passed 274 focused policy, codec, parser, render-profile, and real-mapper tests. Scoped Ruff passed and strict scoped BasedPyright reported zero diagnostics. Formal review resolved one HIGH duplicate-enumeration finding and three MEDIUM findings covering roundtrip asymmetry, mapper fallthrough, and semantic enumeration width; the final audit is PASS with no open findings.

## Notes

Paused S32 render-profile digest, provenance schema, and generator integration work remains uncommitted. Two broad provenance tests still fail only because that S32 WIP has not yet completed its required profile arguments and manifest fixtures; they were excluded from the S41 selector. A broader filing and registry lane passed 173 tests and exposed 23 adjacent pre-existing S38 strict-blank and XML-verifier failures on fields without S41 policies; no S41 policy path failed. These boundaries are recorded for the follow-on fixed-width work and do not expand this Step.
