---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7383c605f96538b2bc9cedc509952132513d6fd2ef381c6adf3cda6867195d53'
step_id: 'S01'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

The register parse returned a bare tuple of rows, so nothing downstream could
distinguish a page that rendered everything from one that rendered a slice. The
parse now yields a typed page carrying both halves of that judgement: the rows
it found and the record total the grid's own pager label states.

## Outcome

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py` gains
  `DeclaracionesRegisterPage`, a strict frozen pydantic model with `rows`,
  `declared_total: int | None` and a derived `truncated` property. `truncated`
  is a property rather than a stored field so the flag cannot disagree with the
  two numbers it is computed from.
- `_parse_declared_total` reads the ZK pager label off the accent-folded,
  casefolded pager text. No pager element means `declared_total is None`, which
  is a one-page result by construction rather than a missing total.
- `_parse_listbox` returns the page on both exits, including the AEAT
  "no results" shape, so the declared total survives even when zero rows
  rendered.

## Verification

`ruff check`, `ruff format --check` and `ty check` clean on the changed module.
Behaviour is covered by the tests recorded under S04, which read both the
paginated synthetic fixture and the real no-pager capture through this parser.

## Notes

The four existing `_parse_listbox` call sites in
`tests/test_declarations_part1.py` were repointed to `.rows` in the same change,
since the return type changed. The pager-label wording has never been checked
against AEAT's live markup: a genuine shape mismatch surfaces as
`declared_total is None` and reads as one page, which is the accepted residual
risk rather than a closed question.
