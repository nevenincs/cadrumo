---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-07-17'
body_hash: 'sha256:ad85aa108a7a790563d0cc4677d5c93ad308e42212a3b35831839f8fe496b58f'
step_id: 'S04'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W01.P01.S04` step record

Scope: `W01.P01.S04` - Strict encrypted-storage roundtrip + anti-tautology test.

## Description

- Add a real encrypted `SecureObjectRepository` roundtrip test for `CalculationRevision` carrying `LedgerFilingEvidence`.
- Populate every defaultable evidence field with a non-default value.
- Assert loaded revision equality and evidence field equality after persistence.
- Assert a mutation that strips evidence is unequal to the original revision.

## Outcome

The persisted calculation-revision envelope now has direct regression coverage proving bundled evidence survives encrypted storage and is not a tautological/no-op field.

## Notes

No production code changes were required for this step.
