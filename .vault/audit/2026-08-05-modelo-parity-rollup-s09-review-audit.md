---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3a33384f3cba0ef8403d3e364fdb6398b62c1e511484d8f0052c4b389eeb3b48'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
---
## Scope

Audit the registry authority path that validates legal and source references for formulas and construct-level evidence, with particular attention to invalid or incomplete references being rejected or explicitly classified.

## Findings

### S09 source reference validation review | low | Registry authority fails closed on invalid source references

`RegistryValidator` and `ValidatedRegistryAuthority` validate construct references before a validated evidence audit is built. A real-authority mutation with an unknown formula source reference is rejected, so the step does not require a new production validator change.

### S09 source reference validation review | low | Incomplete construct references remain visible as unresolved

The construct evidence ledger preserves a construct with incomplete source references and reports status `unresolved`; it does not silently omit the construct or mark it grounded. This closes the intended classification boundary while leaving the underlying authority data unchanged.

## Recommendations

Keep the existing authority validation as the single source-reference gate and keep the construct evidence ledger as the reporting surface for incomplete-but-measurable constructs. Future model parity work should consume these statuses rather than adding a second source-reference validator.
