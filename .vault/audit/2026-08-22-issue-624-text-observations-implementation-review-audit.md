---
tags:
  - '#audit'
  - '#issue-624-text-observations'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:bb3b3de2b0641c9bd7d30eb6ef1910ad9cf34be507f1bd627e1a8f98e2e0039b'
related: []
---



# `issue-624-text-observations` audit: `Grounded text observation implementation review`

## Scope

Fresh-context review of implementation commit `7398a658ae2d44e0874cd1602b612f1d4013b231`
against its parent, limited to GitHub issue 624. The review covered the eight
changed files, the `CasillaObservation` discriminated scalar contract, formula
runtime materialisation, Decimal-only derived projections, application-layer
revision construction, calculation-revision projection validation and identity,
encrypted observation persistence, and the governing filing-period casilla ADR,
plan, and prior audit.

Current `HEAD` was verified as the implementation commit before review and again
before this report. The changed-file Ruff gate passed. Focused pytest runs proved
73 tests passing across the changed observation, declaration-period, repository,
and calculation-revision suites, then 23 further tests passing across formula
runtime, cross-boundary, revision-stamp, and encrypted calculation-repository
coverage. The remaining selected tests could not reach the implementation under
review because registry setup refused the unrelated source
`boe-modelo-194-form-layout` with a byte-count mismatch; every reported failure
and setup error in those runs had that same registry-authority prerequisite as
its root cause.

## Findings

No critical, high, medium, or low implementation findings were identified. The
text discriminator round-trips without Decimal coercion, the runtime replaces
the former structural Decimal zero with the validated text input, every flat
`casilla_values`/`values` projection remains Decimal-only, and persisted typed
envelopes preserve the text scalar and its legal/source grounding.

## Recommendations

No implementation remediation is recommended. Issue 624 is safe to integrate
and close on the reviewed commit. The unrelated
`boe-modelo-194-form-layout` source-byte mismatch should be reconciled by its
own current work owner so registry-backed suites can execute end to end; it is
not attributable to this commit and does not expand this audit's issue scope.
