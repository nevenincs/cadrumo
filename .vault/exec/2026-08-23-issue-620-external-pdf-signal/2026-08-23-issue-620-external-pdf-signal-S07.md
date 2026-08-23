---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:efa66e67feef6856faf40531d3a02781044976e8834a892899b6053a38fa5dcd'
step_id: 'S07'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Add Modelo 130 production-parser regressions for printed-box discovery and zero fabricated blank values

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m130_external_layout.py`

## Description

Load the strict M130 plain and fillable candidate sidecars without promoting their unverified source class.

Extract physical PDF words and require exactly one configured right-column box-number anchor for every target from 01 through 19.

Run every configured target through the production extraction primitives and partition the complete outcome set.

Run Ruff against the new module and pytest against only its two candidate cases.

## Outcome

Both external layout candidates expose all 19 configured M130 box anchors exactly once. This establishes that the blank-result assertion is not passing because the form or its box numbers were unreadable.

Both candidates classify exactly 19 targets as missing, with zero extracted values, zero malformed targets, and zero ambiguous targets. Blank printed boxes therefore cannot fabricate a monetary amount on either physical layout.

The focused Ruff check passed. The focused pytest module passed both cases in 58.02 seconds.

## Notes

The candidates remain explicitly unverified third-party-hosted layouts. The filing-year and period coordinate selects the current registry profile only and is not attributed to either PDF.

No production parser or registry file changed.
