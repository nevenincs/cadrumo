---
tags:
  - '#audit'
  - '#period-grammar-standardisation'
date: '2026-06-11'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
  - '[[2026-06-11-period-grammar-standardisation-adr]]'
---

# `period-grammar-standardisation` Code Review

<!-- Persistent log of audit findings appended below. -->

## PERIOD-001 | INFO | No findings in IVA authority-source Period slice

Review of commit `62142e93b` found no regressions in the IVA wallet authority-source
period migration. The reviewed slice types authority-source `source_periods` as
`core.Period`, converts prefilled bare registry tokens at the application boundary,
renders reports from `Period.registry_token`, and keeps upstream prefill reports token-based.

Verification reported by the reviewer: focused tests passed with `65 passed`, and a direct
pydantic JSON roundtrip for `IvaCompensationAuthoritySource.source_periods` serialised to
the separated `{"filing_year": ..., "code": ...}` shape and validated back equal.

Residual risk: full-repository and vault checks were not run for this review.

## PERIOD-002 | LOW | Overview fallback still documents a dead combined parser bridge

Review of commit `e6a54068f` found the parser cleanup itself matches the rollout intent:
combined forms refuse, and raw AEAT `nT` only resolves with `ejercicio`.

The remaining issue is in `src/aeat/application/overview/_calendar.py`: `_obligation_period_to_core`
still comments and documents that `parse_canonical_period` handles combined forms, then calls
it without `ejercicio`. After the parser cleanup, that branch no longer handles those forms.
Normal schedule obligations pass `core.Period` and bypass this path, so the risk is stale
fallback documentation rather than a known runtime regression.

This was not fixed in the parser cleanup commit because `src/aeat/application/overview/_calendar.py`
currently contains non-authored WIP in the shared worktree.

Verification reported by the reviewer: `src/aeat/domain/tests/test_period.py` passed with
`41 passed`, and registry schema/query tests passed with `50 passed`.

## PERIOD-003 | INFO | No findings in stale guidance cleanup

Review of commit `44851e0de` found no issues. The updated deadline error suggestion uses
the separated `--year 2024 --period 1T` CLI shape, and the raw declaration/justificante
schema docstrings no longer describe combined calendar strings as canonical backend
periods.

Local verification before commit: ruff passed for the touched files, core error-registry
tests passed with `14 passed`, justificante secure-storage roundtrip passed with
`1 passed`, and CLI import smoke printed `OK`. A declaration parser boundary test could
not collect because the shared worktree currently lacks `AeatError` from the parser
boundary support module; that failure was outside this slice.

## PERIOD-004 | INFO | No findings in review-filter example cleanup

Review of commit `1f2c3e68d` found no issues. The commit only changed one docstring
example in `src/aeat/application/review/_errors.py` from a year-qualified hybrid period
to a bare token example, with no behavior path touched.

## PERIOD-005 | INFO | No findings in stale combined fixture cleanup

Review of commit `142889811` found no issues. The changed fixtures moved typed model
fields to `Period.from_year_and_code(2026, "1T")`, and review filter tests now use
bare `period=1T` with separate `year=2026` where applicable.

Verification reported by the reviewer: focused tests for the touched files plus ledger
period grammar produced `136 passed, 22 failed`. The failures were isolated to
`src/aeat/application/auth/tests/test_operator.py` with the known shared-worktree
`ProfileKeysRegistrationError` registration issue; the reviewed period, review, and
submission coverage passed.

## PERIOD-006 | INFO | No findings in export period fixture cleanup

Review of commit `2aaa7d3fb` found no issues. The touched export tests now pass
`Period.from_year_and_code(...)` into typed `build_draft` and `ModeloPresentado`
surfaces without adding combined-string tolerance or weakening the byte-position and
SHA-backed golden export assertions.

Verification reported by the reviewer: focused export model and fichero-BOE roundtrip
tests passed with `28 passed`.
