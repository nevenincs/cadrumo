---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-04-registry-reviewability-gate-code-review-audit]]'
---

# `schema-hardening` audit: `Validator module reviewability baseline`

## Scope

Execute `W04.P08.S38` from the registry hardening next-work plan. This audit
measures validator module sizes after the TOML gate tightening exposed that the
full reviewability test file still has a validator-module failure.

## Findings

- FAIL: `test_registry_validator_modules_stay_below_p05_reviewability_baseline`
  fails on `_validate_relation_periods.py`.
- FAIL: The reviewability test reports `_validate_relation_periods.py` at 240
  `splitlines()` lines against its committed 203-line baseline.
- PASS: No other validator module is reported above its committed baseline by
  that test.
- OBSERVED: PowerShell `Measure-Object -Line` reports 212 non-empty lines for
  `_validate_relation_periods.py`; the regression gate intentionally counts
  blank lines through Python `splitlines()`, so the repair target is the
  test-reported 240-line count.

## Current largest validator modules

| Non-empty lines | Module |
| ---: | --- |
| 283 | `_validate_cross_revision.py` |
| 243 | `_validate_revision_sections.py` |
| 219 | `_validate_record_sections.py` |
| 213 | `_validate_semantic_roles.py` |
| 212 | `_validate_relation_periods.py` |
| 190 | `_validate_references.py` |
| 185 | `_validate.py` |
| 175 | `_validate_revision_context.py` |
| 165 | `_validate_relation_sources.py` |
| 164 | `_validate_dependency_sections.py` |

## Recommended next step

Reduce `_validate_relation_periods.py` below its existing 203-line baseline
without changing validator semantics and without raising the baseline.

## Verification

Failure reproduced with:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_validator_modules_stay_below_p05_reviewability_baseline -q`
