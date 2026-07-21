---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S78'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M347 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Rebaseline the M347 authorization fragment against the live data-fidelity evidence.
- Confirm `authorization.d/347.toml` declares `renta_years = [2024, 2025]` and the live enrolling test path.
- Close the stale-open manifest row without changing source code.

## Outcome

Closed as current-code satisfied. The access-gate tests and global authorization meta-test accept the M347 manifest claim.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed, including the authorization manifest and meta-gate tests.
