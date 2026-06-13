---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S31'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P05.S31`

Authored and wired the off-load-path full-Diseño coverage advisory
report: a non-blocking inventory that compares a modelo revision's
declared casillas against the full AEAT Diseño de Registros casilla set
and surfaces the coverage gap without redding the load.

- Modified: `src/aeat/domain/calculations/registry/_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`

## Description

The ADR amendment separates two concerns: calculation-completeness is
enforced at the snapshot-build load path (the bounded calculation-closure
gate), while full-Diseño coverage is an advisory inventory produced off
the load path. The full-Diseño extraction
(`derive_diseno_coverage_casillas`) already existed; this Step builds the
report producer on top of it.

`DisenoCoverageReport` is a frozen dataclass carrying, for one modelo
revision: the full `(segmento, number)` casilla set the AEAT Diseño
declares (`diseno_casillas`), the subset the registry also declares
(`covered_casillas`), and the subset the Diseño declares that the
registry does not (`coverage_gap_casillas`) — the advisory follow-up
inventory. Convenience count properties (`diseno_casilla_count`,
`covered_count`, `coverage_gap_count`) summarise the inventory.

`build_diseno_coverage_report(path, modelo_id, revision, *,
multi_segment)` produces the report: it extracts the full Diseño casilla
set and partitions it against the revision's declared
`(segmento, number)` identities into covered and gap subsets. The
comparison is segment-aware for multi-segment modelos. The report is
strictly off-load-path — it parses the multi-megabyte Diseño corpus — and
is purely advisory: a coverage gap reported here never fails a modelo,
because the load-blocking enforcement is the bounded
calculation-completeness gate, not full-Diseño coverage.

Both new symbols are re-exported from the registry package
`__init__.py`. A test in `test_record_design.py` exercises the report
against the Modelo 200 2024 corpus Diseño, asserting that the three
casilla sets partition the full Diseño coverage (covered plus gap equals
the full set, covered and gap disjoint) and that the gap is non-empty —
Modelo 200's Diseño is overwhelmingly accounting-statement data-entry
fields outside the calculation surface, the deliberate counterpart to the
bounded gate. Building the report does not raise: an advisory inventory
never reds a load.

## Tests

`pytest test_record_design.py` — 40 tests pass, including the new
advisory-coverage-report partition test; `pytest test_schema_hygiene.py`
— 11 tests pass. `ruff check` clean on all three touched files.
