---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:da15bba72c737af3e35209e16c0ae1583d10eedd3366a3d8391e7ac3c4314db7'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: `S121 code review`

## Scope

Independent review of `P05.S121` across source predecessor `5c43de30cf`, evidence commit `be894391b175b24363d593cc03df0a1b167e979a`, the extracted Sede capture module, its application consumer, direct tests, the size-budget gate, and the CI-lane decisions.

## Findings

### s121-exec-line-count | low | Execution evidence understates the reviewed module size

The S121 execution note said `declarations.py` measured 937 lines. Both the named predecessor and the current reviewed path measure 1,058 lines. The module remains below the 1,250-line limit and is absent from the size-gate findings, so this did not invalidate the completed refactor; it did make the execution evidence inaccurate.

### s121-exec-line-count-staged-reintroduction | low | Pending index version restores the corrected error

Commit `9764465dad` correctly changes the execution note to 1,058 lines. At review time, the shared Git index contains a staged version of the same record that restores the old 937-line text. The committed correction is therefore valid, but the staged record must not be committed unchanged.

## Recommendations

Keep the S121 execution note at 1,058 lines when resolving the current staged record. Retain the existing failing-fixture boundary: `RoutedRegisterDocuments` returns 204 for every non-navigation request, so it cannot truthfully exercise Cotejo/PDF or submitted-file capture without a separately grounded real-protocol fixture.

## Verification

At `9764465dad`, the S121 execution record reports 1,058 lines, exactly matching `declarations.py` in both predecessor `5c43de30cf` and the current source tree. The source remains below the 1,250-line budget and neither the source nor evidence commits alter `dev/audit/size_budget.py` or its baseline.
