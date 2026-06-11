---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
step_id: 'S25'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace period-grammar-standardisation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Replace the period: str fields in the iva prorrata, submission, verification schema, filing schema and modelo export models with core.Period

## Scope

- `src/aeat/domain/iva/_prorrata.py`
- `src/aeat/domain/submission/_models.py`
- `src/aeat/application/verification/_schema.py`
- `src/aeat/domain/filing/_schema.py`
- `src/aeat/application/modelo/_export.py`

## Description

Cluster F scope only (verification/_schema): `VerificationVerdict.period` migrated from
`str` to `aeat.core.Period`. Remaining files from the original S25 scope
(`iva/_prorrata.py`, `submission/_models.py`, `filing/_schema.py`, `modelo/_export.py`)
are out of scope for this execution run and remain as `str` for a follow-up cluster.

- Added `Period` import to `application/verification/_schema.py`; replaced `period: str = Field(...)` with `period: Period`
- Updated module docstring to document the `Period` JSON serialisation shape (`{"filing_year": YYYY, "code": "..."}`)
- Updated `VerificationVerdict` attribute docstring
- Added `Period` import to `application/verification/_verify.py`
- Replaced `_registry_period` + `_filing_period_date` helpers with single `_parse_period(period, ejercicio) -> Period` bridge that calls `parse_canonical_period` + `Period.from_year_and_code`
- Updated `verify_declaracion` to call `_parse_period` once, pass typed `period` to `_load_snapshot` and `period_end_date` directly, and pass `period` (typed `Period`) to `VerificationVerdict`
- Updated `_load_snapshot` signature to accept `period: Period` and use `period.filing_year` / `period.registry_token` for the authority snapshot call
- Removed now-unused `from datetime import date` import
- Updated `TestVerdictJsonRoundTrip.test_verdict_is_json_serialisable` to construct `Period.from_year_and_code(2025, "1T")` and assert round-trip equality plus the reloaded `period` field value

## Outcome

- Import smoke: `aeat.entrypoints.cli` import prints OK
- `pytest src/aeat/application/verification/tests/ -q --tb=short`: 31 passed in 2.22s
- `ruff check` on all three changed files: all checks passed
- No new `"\d{4}Q[1-4]"` literals in production files
- Commit: `17c3f8f23` — `refactor(verification): typed core.Period on VerificationVerdict (W02.P08 cluster F)`

## Notes

The remaining four files from S25 (`iva/_prorrata.py`, `submission/_models.py`,
`filing/_schema.py`, `modelo/_export.py`) were NOT touched; they involve encrypted-SQL
persistence boundaries (D, E) and separate vocabulary concerns (G) per the S31
discovery note and require separate execution runs.
