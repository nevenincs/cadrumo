---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:1d971ef5f5e0660d112d123a455b21e67a941ccdcabacd40d00e0929208a1fe7'
related:
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
---

# `modelo-parity-rollup` audit: `S02 conformance comparator review`

## Scope

Reviewed the bounded W01.P03.S02 implementation against the accepted five-domain parity ADR, the denominator research, and the year-specific dictionary/layout source contracts. The review covered the retired module, the retired test, the real bundled registry, and the focused verification gates.

## Findings

### conformance-projection | medium | The bounded comparator is not yet projected into the registry-wide report

`compare_annual_casilla_population` now provides a safe, authority-selected comparison for one exact snapshot, but the existing registry-wide conformance profile and CLI do not invoke or render it. The measured 2024 and 2025 divergences therefore remain available through the bounded API and tests, not yet through the standard report. Keep this open for the later annual-matrix and classification steps; do not make the generic profile infer filing years or periods.

### printed-form-boundary | low | Dictionary identity must not be reported as printed-form parity

The implementation correctly reports dictionary identity as measured while retaining BOE printed-form membership as `unsupported`. The source references alone do not establish printed-form membership, so this is an explicit residual evidence boundary rather than a defect.

### attribute-boundary | low | XSD-only and unprojected attributes remain unmeasured

The parser exposes field identity, path, data type, and casilla identity, but no contract maps all source attributes to registry casilla attributes. The comparator therefore leaves XSD-only and unmapped attributes `unsupported` or `unmeasured`; later work must add a source/parser contract before claiming attribute parity.

### test-evidence-anchors | low | Fixed annual census anchors now prevent parser-self-confirmation

The focused tests use the real bundled authority and also assert the observed annual populations and identity divergences: 2024 has 2,093 registry casillas versus 2,062 dictionary casillas and 31 identity divergences; 2025 has 2,238 versus 2,205 and 33 divergences. This keeps the test evidence independent of deriving every expected count from the production comparator.

## Recommendations

- Carry `conformance-projection` into W01.P03.S03/W01.P07.S13 and project only exact finite annual coordinates into the standard report.
- Preserve the `unsupported` and `unmeasured` classifications until an authoritative printed-form or XSD attribute parser is explicitly grounded and tested.
- Update the fixed census anchors only when the bundled official source or the year-specific registry declaration intentionally changes, with a corresponding audit entry.

## Verification

- the historical check â€” 25 passed.
- the historical check â€” all checks passed.
- the historical check â€” 2 files already formatted.
- the historical check â€” 0 errors, 0 warnings, 0 notes.
- `git diff --check` on the owned files â€” clean.
- The delegated reviewer persona was invoked but did not return a report before shutdown; the supervisor completed this evidence-backed review and recorded the residual projection finding above.
