---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:7f7b2909b7c72795ce550b7fff20616bf6b4942e1d610acd9ef1f43a72d0c62c'
step_id: 'S64'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M210 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Rebaseline the M210 authorization fragment against the recorded enrollment years.
- Confirm `authorization.d/210.toml` declares `renta_years = [2025, 2026]`, `evidence_class = "calculation"`, and the live enrolling test path.
- Close the stale-open manifest row without changing source code.

## Outcome

Closed as current-code satisfied. The access-gate tests and global authorization meta-test accept the M210 manifest claim and enrollment evidence.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed, including `src/aeat/core/access_gate/tests/test_authorization_manifest.py` and `src/aeat/tests/test_modelo_authorization_gate.py`.
