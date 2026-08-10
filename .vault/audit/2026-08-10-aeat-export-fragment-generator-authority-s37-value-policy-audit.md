---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c8b39ad87333ef703edd914150879cc76fa368c9e44812e83c0720ee4b93e851'
related: []
---
# `aeat-export-fragment-generator-authority` audit: `s37 value policy`

## Scope

Independent review of `W02.P03.S37` against the accepted generator-authority ADR, the approved plan, and the completed S31 render-profile contract. The review covered the public `ExportValuePolicy` axis and projector, strict schema shape matrix, fixed-width parser wire validation, filing writer and verifier, record-plus-field policy identity, active registry renderer reuse, S31 profile enum reuse, loader-semantic normalization version 2, structural canonical-home guards, and the absence of S32 generator integration, legacy fallback, or implicit policy inference.

Independent verification passed 121 focused policy, filing, renderer, render-profile, and provenance tests plus 68 broader registry-schema, export-parser, and implicit-decimal tests. Scoped Ruff passed; strict BasedPyright reported zero errors, warnings, or notes; and the scoped relative-import gate passed. `vault check all` exited successfully with repository-wide historical warnings. The feature check retained only the shared-tree stale-index warning caused by concurrently added feature records.

## Findings

No critical, high, or medium findings. The one low finding below was resolved and independently reverified before review close.

### public-projector-exception-closure | low | A signalling Decimal NaN escapes the declared validation error boundary

`project_export_value` accepts an arbitrary object and otherwise converts invalid selected/unselected inputs into `RegistryValidationError`, but `Decimal("sNaN")` raises `decimal.InvalidOperation` while evaluating equality against zero. Validated `ModeloValue` instances already reject non-finite decimals and the active registry renderer supplies strings, so the reviewed production routes do not expose this edge. The exported public projector nevertheless does not fully honour its strict invalid-value refusal contract for every accepted runtime object shape.

Resolution: resolved in the reviewed snapshot. The projector now rejects non-finite `Decimal` and float inputs before equality, including signalling NaN, quiet NaN, and infinities. The focused projector suite passed 57 tests after the change; scoped Ruff and strict BasedPyright remained clean.

## Recommendations

- `public-projector-exception-closure`: completed by explicit finite-value refusal and direct signalling-NaN, quiet-NaN, and infinity regressions. No follow-on ADR is required.
