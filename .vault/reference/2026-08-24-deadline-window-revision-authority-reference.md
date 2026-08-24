---
tags:
  - '#reference'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e32ae98c561e93f8b761aa47e4197760ac569b91a37205d7f00c1e9f484a40d7'
related:
  - '[[2026-08-24-deadline-window-revision-authority-research]]'
---

# `deadline-window-revision-authority` reference: `deadline selection call graph and defect inventory`

## Summary

The canonical resolver is `select_revision` in
`src/cadrumo/domain/calculations/registry/_temporal.py`; snapshot construction uses it,
but `deadline_windows(year)` in `_authority.py` emits every nested matching row.

Validation is assembled under `domain/calculations/registry/_validate.py`; the new
ownership invariant belongs there. Its coordinate is `(modelo, period.filing_year,
period.registry_token, typed qualifiers)`, with redundant window `filing_year` equal to
the period year. Following-year filing dates remain in `opens_on` and `closes_on`.

Repair inventory: M190/M193 align the redundant year; M210 replaces duplicated quarter
keys with the typed `EVENT-N`/`0A` plazo design; M303 retains rows only in the exact
owner including the 2024 cutover; M322 removes two 2023 copies from `2008-2022`; M353
removes three 2025 copies from `2026-y-siguientes`. Periodic completeness repair also
materialises missing selector periods for M303, M322, M353, and M369. Open-ended
revisions need an explicit supported-through year so the gate demands complete closed
years without pretending future calendar dates are already known.

The consumer chain is authority to `DeadlineEngine.compute` to overview projection and
CLI calendar/agenda/backlog. Filing-window lookup, workflow gates, and explain share the
same source. Registry repair restores parity without downstream dedupe.

Required tests: minimal invalid-model validator bite, bundled all-modelo
ownership/uniqueness sweep, historical 2025 engine schedule, and real CLI JSON
multiplicity coverage.
