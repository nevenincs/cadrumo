---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f83b6ce003259282156cde8f15a61ca325c42cb9e698350d8f7e924af521c2f2'
step_id: 'S13'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Prove parser completeness, declared totals, source applicability, and source-hash enforcement

## Scope

- `dev/registry/tests/`

## Description

- Extend the real bundled-workbook intermediate test to compare every fixed parser record and field against the shipped parser output and verify each declared total against terminal extent.
- Preserve and assert the typed variable-envelope evidence separately from the fixed-record set.
- Add loader-boundary refusals for an inapplicable filing-year source, a wrong design epoch, and catalogue SHA-256 drift before parser projection.
- Add an AST structural gate limiting the intermediate loader to catalogue binary selection and the shipped parser, preventing derivative or legacy fallback access.

## Outcome

The parser-to-generator handoff is now proven complete for the hash-verified M200 official workbook. Every fixed record retains source coordinates and a declared total matching its parsed extent; selection rejects an inapplicable epoch and a digest-drifting source before parsing; the loader cannot silently add a derivative input path.

Focused verification passed: `pytest` for the S13 IR suite (5 passed) and the combined IR plus source-selection suite (10 passed); Ruff check and format check; and basedpyright on the changed test module.

## Notes

The independent review recorded no critical, high, medium, or low findings in `2026-08-10-aeat-export-fragment-generator-authority-s13-parser-completeness-audit`.

The repository-wide `just test-ratchets` checkpoint remains red outside this scope: marker discipline in the operator-surface contract test, one absolute registry-test import, and pre-existing campaign-metadata comments. The S13 module was not named by that gate.
