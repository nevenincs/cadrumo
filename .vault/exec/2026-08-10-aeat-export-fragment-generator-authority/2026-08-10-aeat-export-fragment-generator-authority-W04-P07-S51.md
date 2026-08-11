---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:f044ff9b0b6bb76a0d75b686c564e816a16709ce0ddbdeec930c5be42d006b18'
step_id: 'S51'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Enforce M303 export applicability before rendering: optional canonical values may emit blank only when law/profile says not applicable, while exonerado, prorrata, differentiated-sector, simplified-regime, amendment, payment, and account populations with missing required authority refuse the whole export. Prove unsupported fields cannot be reclassified as filler, header defaults, or legacy lookups

## Scope

- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add one immutable explicit applicability envelope for the S47 through S50 M303 units.
- Validate annual-summary, prorrata, differentiated-sector, simplified-row, and producer authority before layout or target creation.
- Remove superseded optional per-unit export parameters and delegate canonical validators and projectors.
- Carry the typed envelope through Modelo export orchestration and real CLI callers without synthesis.
- Refuse missing, ambiguous, unsupported, defaulted, or payload-on-nonapplicable units with no artifact.

## Outcome

M303 export now requires one explicit typed whole-unit applicability decision. Complete units pass the pre-layout boundary for all five epochs and reach the intentionally withdrawn-layout refusal without an artifact. Missing applicable facts, absent envelopes, invalid producers, and non-M303 envelope misuse refuse earlier. Explicit non-applicability is the only blank authority.

Application and Modelo lanes passed, including 12 Modelo tests and a real CLI integration test. Ruff and targeted Basedpyright passed. Independent review passed with zero findings.

## Notes

Initial review found that the lower filing gate was not propagated through production Modelo orchestration. The typed envelope was threaded through command, temporary-write, filing, CLI export, review-package, and quickfile paths, then re-reviewed successfully. M303 layouts remain withdrawn for S19 and S20.
