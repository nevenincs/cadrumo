---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:83b4a9a75095dc675d12801ae49efaa2300f3a082309f859aac1109e55ddae3c'
step_id: 'S03'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# widen the xml dictionary casilla-id parser beyond digits-only and regression-test the 2024 and 2025 M100 id conventions

## Scope

- `src/cadrumo/domain/calculations/registry/_export_parse.py`

## Description

- Replace the digits-only parser with the exact official digits-or-one-uppercase-letter grammar.
- Preserve exact source spelling and refuse placeholders, lowercase, multi-letter, and mixed identifiers.
- Prove numeric and annex identifiers from real bundled Modelo 100 2024 and 2025 dictionary rows.

## Outcome

Completed with 23 parser and official-box dependency tests passing. The combined integration lane passed 80 tests. Scoped Ruff, formatting, `ty`, BasedPyright, and diff checks passed. Formal review approved with zero unresolved critical, high, or medium findings.

## Notes

No compatibility reader, normalization rule, alias, fake source, mock, stub, patch, skip, or xfail was introduced.
