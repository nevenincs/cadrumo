---
tags:
  - '#audit'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d61ff008a785cbc00127b9a30ee9133f558e60efb6ac2acc4e209b0e339befe5'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# `registry-suite-red-at-head` audit: `P02 S05 deduction authority and S11 oracle review`

## Scope

Audit the P02.S05 fixture sweep against the production deduction-kind authority, then verify that the P02.S11 AEAT worked examples execute their unchanged numeric assertions sequentially.

## Findings

### impossible-aic-distractor | high | The first repair still used a category and flow pair production cannot mint

The initial sweep replaced an intra-community acquisition on `soportado` with the same recipient-only category on `repercutido`. Production always resolves that category to `inversion_sujeto_pasivo`, so the negative selector row remained impossible.

Resolution: replace the distractor with a domestic recipient reverse-charge observation carrying `DOMESTIC_CURRENT` deduction evidence. It is production-reachable and remains outside the intra-community selector by category. The exact selector test passed after the repair.

### final-review | low | No open findings remain

The shared fixture helper calls the production `required_deduction_evidence_authority` mapping; callers state only the legal deduction kind and evidence locator. Recargo-equivalencia rows remain authority-free because the production observation validator explicitly exempts that category. No fake, stub, mock, patch, skip, xfail, mirrored business mapping, or weakened AEAT expectation was introduced.

The exact post-repair M322, M353 and M390 manual route passed eleven tests sequentially. Their expected AEAT figures were unchanged.

## Recommendations

Close P02.S05 and then P02.S11. Continue to treat full export-layout failures in the separate P03 registry-data rows rather than absorbing them into this fixture sweep.
