---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S76'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M151 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Rebaseline the M151 authorization fragment against the live enrolling test.
- Confirm `authorization.d/151.toml` declares calculation evidence for renta years 2024 and 2025.
- Close the stale-open manifest row without changing source code.

## Outcome

Closed as current-code satisfied. The authorization manifest and meta-gate accept the M151 recorded year set.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed, including the authorization manifest and meta-gate tests.
