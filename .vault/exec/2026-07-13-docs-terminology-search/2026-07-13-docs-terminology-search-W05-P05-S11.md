---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:51def0866609aeb8a5a1487cf195512fbdf402a5df8c03fa33f868612c36ad35'
step_id: 'S11'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Declare the closed ResultDisplayClass StrEnum and the single derivation function (record kind + concept domain + page path prefix to class) beside the unified record, with a unit gate proving every projected record maps to exactly one class

## Scope

- `dev/docs/terminology/_unified_record.py`
- `dev/docs/terminology/tests/test_unified_record.py`

## Description

- Declare the closed `ResultDisplayClass` StrEnum (`casilla`, `modelo`, `cli`, `technical`, `doc`) beside the unified record, documented and exported in `__all__`, orthogonal to the producing-surface record kind.
- Add the single derivation authority `derive_display_class(record)` over `_display_class_for(kind, domain, target)`: CASILLA records map to `casilla`; CLI to `cli`; a CONCEPT card splits by Handbook domain (`modelo` domain to `modelo`, every other domain to the general-fact `doc`); a full-text page splits by path prefix (`cli/` to `cli`, `api/` to `technical`, everything else user-facing to `doc`). The function is total over every record kind, so no record falls through to a null class.
- Read the concept domain from `metadata.domain` (`None` for non-concept kinds) and the page path from `target`, so a finished unified record derives its class from data already on the record.
- Add a coverage gate that walks the same injected projection the injection consumes (approved concept cards, the full casilla projection, constructed CLI command/option records) and asserts every record derives exactly one valid member, with dedicated derivation checks for the concept domain split and the page path split.

## Outcome

- Every projected record derives exactly one valid `ResultDisplayClass`; an unmapped or null-class record is a gate failure. The coverage gate exercises the real corpus (over one thousand records) plus a constructed `technical` page hit so all five classes are proven reachable.
- The gate suite passed (nineteen tests green across the coverage gate, the ladder gate, and the existing unified-record suite; the full terminology test folder at one hundred eight passed).

## Notes

- The coverage gate landed as a dedicated new test module rather than inside `test_unified_record.py` (a coordinator-directed split): it keeps the display-class coverage isolated and avoids edit collision with the concurrently-landing casilla work on the shared unified-record test file. The plan-row scope named the unified-record test file; the actual home is the sibling coverage module, functionally equivalent.
- Built on preserved uncommitted working-tree WIP from a crashed prior session (the enum plus the derivation core were already correct); verified the `ConceptDomain` import resolved to the Handbook package facade rather than trusting it.
