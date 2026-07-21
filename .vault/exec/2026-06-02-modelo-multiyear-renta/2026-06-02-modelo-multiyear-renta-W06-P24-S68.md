---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S68'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M714 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Enroll Modelo 714 in the directory-mode authorization manifest.
- Set the recorded renta years to 2023 and 2024.
- Point the manifest at the two-year art.31 joint-limit calculation enrollment test.

## Outcome

- Satisfied by `authorization.d/714.toml`.
- The authorization gate accepts the Modelo 714 manifest entry and matching enrollment evidence.
- Verified by `uv run --no-sync pytest -q -n 0 src/aeat/core/access_gate/tests/test_authorization_manifest.py src/aeat/tests/test_modelo_authorization_gate.py`, which passed 9 tests.

## Notes

- The manifest authorizes the current calculation evidence for 2023 and 2024 only.
