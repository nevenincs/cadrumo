---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:922cbf7bd2c190293c556dc308d488203f73074cee1f26eafbc1cb2fd821561a'
related: []
---

# `schema-hardening` audit: `Registry reviewability gate headroom`

## Scope

Execute `W03.P07.S35` from the registry hardening next-work plan. The audit
measures the committed registry TOML corpus before tightening the regression
gates. It does not move registry data and does not change loader or schema
semantics.

## Findings

- PASS: The committed registry corpus contains 15,345 TOML files under
  `src/aeat/_data/registry/aeat/modelos`.
- PASS: No registry TOML file exceeds 1,500 lines.
- PASS: No registry TOML row exceeds 600 characters.
- OBSERVED: One registry TOML file remains above the 1,200-line review band:
  at 1,218 lines.
- OBSERVED: Two registry TOML files are above 1,000 lines.
- OBSERVED: Six registry TOML files have at least one row wider than 550
  characters.

## Largest files

| Lines | Max row | Path |
| ---: | ---: | --- |
| 1,218 | 290 | the retired data file |
| 1,039 | 542 | the retired data file |
| 969 | 153 | the retired data file |
| 969 | 153 | the retired data file |
| 954 | 431 | the retired data file |
| 940 | 431 | the retired data file |
| 932 | 305 | the retired data file |
| 912 | 431 | the retired data file |
| 900 | 44 | the retired data file |
| 900 | 499 | the retired data file |

## Widest rows

| Max row | Lines | Path |
| ---: | ---: | --- |
| 572 | 10 | the retired data file |
| 552 | 21 | the retired data file |
| 552 | 14 | the retired data file |
| 552 | 21 | the retired data file |
| 552 | 21 | the retired data file |
| 552 | 21 | the retired data file |
| 550 | 10 | the retired data file |
| 545 | 9 | the retired data file |
| 542 | 1,039 | the retired data file |
| 528 | 8 | the retired data file |

## Gate recommendation

- Tighten the corpus hard cap from 5,000 lines to 1,500 lines.
- Tighten the corpus row-width hard cap from 1,200 characters to 600
  characters.
- Tighten the baseline assertion from 3,500 lines to 1,250 lines, keeping a
  small allowance above the current 1,218-line M123 file.
- Tighten the baseline row assertion from 1,000 characters to 575 characters,
  keeping a small allowance above the current 572-character row.
- Keep M123 visible as the only current soft-band follow-up candidate.

## Verification

This audit was produced from a direct scan of committed TOML files under the
registry modelos directory. The next step owns changing the test constants and
running the focused registry reviewability tests.
