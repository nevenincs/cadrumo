---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S294'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-MARC-C ledger import --period rejects 2026T1 silently with no suggestion of valid format 2026-Q1

## Scope

- `rejection message should suggest the canonical period token form when bare-shape input fails parsing`
- `previously logged as S239 R7-MARC-D4  -  re-confirmed open in round-8`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Ground S294 with RAG against the cross-domain plan, period-grammar plan, and current ledger import parser.
- Verify that production already routes `ledger import --period` through the shared strict `_optional_canonical_period` parser.
- Add a real CLI regression for `ledger import` with `--period 2026T1 --year 2026` and a real CSV dry run.
- Assert the refusal names the bad token, teaches the current canonical `1T` plus `--year` grammar, and does not revive the retired `2026-Q1` notation.
- Run the full ledger period grammar integration file and touched-file ruff.

## Outcome

- Closed S294 with a regression-only change. No production code was needed.
- The current canonical operator grammar is `--period 1T --year 2026`; the old testimonial wording that expected `2026-Q1` is superseded by the period-grammar standardisation work.
- Validation passed with `43` ledger period grammar integration tests.

## Notes

The older `W09.P45.S239` row tracks the broader historical period-grammar issue and remains open in the plan. This S294 closure only pins the round-8 `ledger import --period 2026T1` testimonial shape against the current canonical refusal guidance.
