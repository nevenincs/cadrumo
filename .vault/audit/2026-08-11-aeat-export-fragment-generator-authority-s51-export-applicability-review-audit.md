---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:a34f1c13158b929f7a3e624b085e44f2590e549127430f4c48b39a8b35f79725'
related: []
---

# `aeat-export-fragment-generator-authority` audit: `s51 export applicability review`

## Scope

Reviewed the S51 whole-export applicability envelope, S47 through S50 delegation, producer completeness, production caller propagation, five-epoch refusal behavior, and the withdrawn-layout boundary.

## Findings

### s51-export-applicability-review | high | Production Modelo orchestration initially omitted the envelope

The filing gate was correct, but the public Modelo export chain did not carry the required typed envelope. Remediation threaded it through the command, Modelo export, temporary writer, filing export, CLI export, review-package, and quickfile paths. Callers without authoritative facts pass explicit absence and receive a typed refusal; none synthesize profile defaults.

### s51-export-applicability-review | low | Final review found no residual defect

The final review confirmed one pre-layout gate, explicit tri-state decisions, exact S47 through S50 delegation, producer revalidation, five-epoch public no-artifact proofs, and no layout reactivation, fallback, alias, or legacy path.

## Recommendations

- Keep whole-export applicability explicit and typed at every public boundary.
- Keep S19 and S20 as the sole owners of M303 map generation and layout reactivation.
- Refuse callers that cannot supply authoritative applicability rather than infer it.
