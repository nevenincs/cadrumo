---
tags:
  - '#audit'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# `declaracion-extraction-architecture` Code Review

DE-REVIEW-001 | HIGH | Declaration tax-id regex rejects valid CIF/legal-entity NIF values

`src/aeat/adapters/inbound/declaracion/_parser.py` now accepts only DNI/NIE-shaped
values in the generic `NIF:` extractor: `(?:[XYZ][0-9]{7}|[0-9]{8})[A-Z]`.
That excludes valid Spanish legal-entity NIF/CIF forms such as `B12345678`,
which are plausible for declaration PDFs and especially relevant to business
modelos in this plan. The previous pattern was broad enough to capture these
identifiers. The fix should preserve the newly supported `NIF Presentador:`
prefix but restore legal-entity NIF coverage and add a parser-boundary
regression test.

Resolution: widened the parser regex to accept letter-prefixed Spanish tax IDs
and added a parser-boundary regression test using `B12345678`. Verified with
`ruff check` and `pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py -q`.
