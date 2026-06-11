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

## PERIOD-007 | INFO | No findings in application period literal cleanup

Review of commit `dcd07b725` found no issues. The workflow mismatch test now passes
the expected annual `Period` while mismatching only the modelo, preserving the intended
assertion. The invoice projection change uses the separated `2026 1T` display label on
a plain string projection field, without altering a typed API.

Verification reported by the reviewer: the targeted workflow mismatch and invoice
projection tests passed with `2 passed`.

## PERIOD-008 | MEDIUM | Ledger check initially still passed a string period

Review of commit `84e899cc9` found that the ledger model migration correctly seated
ledger filters, import/export payloads, preflight, and status reporting on `core.Period`,
but the CLI `ledger check` path still constructed `period=str(year)` before calling
`preflight_transaction_catalogue`. That API now resolves the supplied period as a
`core.Period` and calls `.contains(...)`, so the string path could crash once imported
transactions were present.

The same review also flagged that `src/aeat/application/ledger/tests/_action_test_support.py`
had temporarily become a broad re-export barrel for production ledger APIs, which weakened
the test import boundary.

Resolution landed in commit `1f3d45569`: `ledger check` now passes
`Period.from_year_and_code(year, "0A")`, and `test_actions_review.py` imports production
ledger APIs directly from the application package while `_action_test_support.py` remains
limited to shared test helpers and fixtures.

Local verification after the fix: ruff passed for the touched files; focused ledger period
tests passed with `71 passed`; ledger link/check verb tests passed with `6 passed`; the
corpus preflight/check regression passed with `1 passed`; CLI import smoke printed `OK`.

## PERIOD-009 | INFO | No findings in ledger check follow-up

Review of commit `1f3d45569` found no remaining issues. The reviewer confirmed that
`ledger check` imports `core.Period` and passes `Period.from_year_and_code(year, "0A")`
into `preflight_transaction_catalogue`, whose typed API calls `.contains(...)` on the
resolved period. The reviewer also confirmed that `test_actions_review.py` now imports
production ledger APIs directly, while `_action_test_support.py` is restricted to shared
fixtures, helpers, and test-only support types.

Verification reported by the reviewer: `test_actions_review.py` passed with `5 passed`,
and the integration ledger link/check verb suite passed with `6 passed`.

## PERIOD-010 | MEDIUM | Readiness no-period fallback was unreachable

Review of commits `94fa01ae7` and `ec84d2fab` found that the direct
`core.Period` pass-throughs were correct for explicit periods: modelo calculation
preflight passes `work_unit.period` directly, and state projection readiness no
longer projects ledger reports through the old aggregation-period adapter.

The review found one medium issue in the state projection no-period path:
`ModeloReadinessRequest(period=None)` still became an empty `period_token` before
profile preflight report construction. Because `ProfilePreflightReport.period`
requires a non-empty token, the intended annual `0A` fallback could not be reached.

Resolution landed in commit `debaac92e`: state projection now resolves
`readiness_period = Period.from_year_and_code(filing_year, "0A")` before profile
preflight and reuses that typed value for profile preflight, registry snapshot
lookup, and ledger preflight. A real projection regression test covers the
no-period request path and asserts the projected annual `Period`.

Verification before the fix: the reviewer ran state projection plus ledger
preflight tests with `27 passed`. Local verification after the fix: ruff passed
for `state_projection.py` and `test_state_projection.py`; the full state projection
test file passed with `16 passed`; CLI import smoke printed `OK`.

## PERIOD-011 | INFO | No findings in readiness annual fallback follow-up

Review of commit `debaac92e` found no remaining issues. The reviewer confirmed
that no-period readiness resolves `Period.from_year_and_code(filing_year, "0A")`
before profile report construction, that the same resolved token is used for
registry snapshot lookup, and that actual ledger preflight receives the typed
`readiness_period`. The reviewer also confirmed the regression test is
non-tautological because it builds real isolated storage/profile state and invokes
the production projection path.

Verification reported by the reviewer: the no-period annual fallback regression
and the explicit-period ledger preflight blocker test passed with `2 passed`.
