---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:89e5d0e1c96fa8e1ee40348b98c81fbac0c839d64028f594eef9ceba596f181c'
step_id: 'S80'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M184 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Rebaseline the M184 authorization fragment against the live data-fidelity evidence.
- Confirm `authorization.d/184.toml` declares `renta_years = [2024, 2025]` and the live enrolling test path.
- Close the stale-open manifest row without changing source code.

## Outcome

Closed as current-code satisfied. The access-gate tests and global authorization meta-test accept the M184 manifest claim.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed, including the authorization manifest and meta-gate tests.
