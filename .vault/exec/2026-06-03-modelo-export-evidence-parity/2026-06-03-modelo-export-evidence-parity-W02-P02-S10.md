---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S10'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W02.P02.S10` step record

Scope: `W02.P02.S10` - Offline export evidence roundtrip test (export -> read back -> evidence reconstitutes the casilla basis).

## Description

- Add a generic ledger-filing-evidence to workbook-evidence projection adapter.
- Require explicit contributor transaction-to-casilla attribution and refuse missing attribution.
- Add an offline export roundtrip test that serializes XLSX plus JSON sidecar, reads both artefacts back, and asserts the casilla evidence basis survives.

## Outcome

Offline workbook exports now have a regression proving the protected `Evidencia` tab and hash-bound evidence sidecar preserve the casilla basis for ledger contributors and manual fact-basis entries.

## Notes

The adapter deliberately does not infer casilla ids from IVA, IRPF, or modelo-specific transaction facts. Callers must supply the attribution map; missing contributor attribution raises `CalcSheetsEngineError`.
