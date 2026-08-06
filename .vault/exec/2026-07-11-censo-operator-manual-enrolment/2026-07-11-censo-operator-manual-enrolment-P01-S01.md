---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:8e6b8dfb38644c299f383a0f06534511fd5c5bfe1fbc66ab9d9b490f4d765a48'
step_id: 'S01'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# Retire the sede live-censo scrape: delete the launcher drive, the G313 parser, their tests, the censo_g313_launcher constant, and the sede package exports

## Scope

- `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`
- `src/aeat/adapters/outbound/aeat/sede/_censo.py`
- `src/aeat/adapters/outbound/aeat/sede/tests/`
- `src/aeat/adapters/outbound/aeat/sede/__init__.py`
- `src/aeat/core/external_constants.toml`

## Description

- Deleted the live-scrape driver `_censo_live.py` (`fetch_g313_censo`, `G313_LAUNCHER_URL`, the read-guard policy, `censo_fact_set_to_mapping`) and the parser module `_censo.py` (`parse_g313_html`, `_G313_LABELS`, `CensoFactSet`, `CensoParseError`) plus their tests `test_censo.py` / `test_censo_parser.py`.
- Dropped the sede package exports for `G313_LAUNCHER_URL`, `censo_fact_set_to_mapping`, `fetch_g313_censo`, and `CensoParseError` from the sede `__init__.py` re-export facade.
- Removed the `censo_g313_launcher` sede-path constant from `external_constants.toml`, its typed field on the `sede_paths` model in `external_constants.py`, and the assertion in `test_external_constants.py`.
- Removed the orphaned `CensoParseError` entry from the adapters error registry and the `test_censo_parse_date_delegates_to_canonical` case (and its docstring mention) from the canonical-homes gate.

## Outcome

The sede live-censo scrape chain is fully deleted (delete-not-stub). No production or test module resolves `parse_g313_html`, `_G313_LABELS`, `censo_g313_launcher`, `_censo_live`, or the sede `_censo` parser. `pytest --collect-only -q src/aeat` collects clean; the sede adapter tests and `test_external_constants` are green.

## Notes

Landed together with `P01.S02` in one atomic explicit-path commit (the sede chain and the CLI verb family reference each other through the application layer). No sensitive data touched; no destructive git operations.
