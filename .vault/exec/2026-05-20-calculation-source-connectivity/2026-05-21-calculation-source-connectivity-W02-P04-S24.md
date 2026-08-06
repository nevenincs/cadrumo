---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-07-17'
body_hash: 'sha256:96a15ac66be9f43b748952e6d0d35351faced27af9301bd8757ace7849a3014e'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# Execution Record: W02.P04.S24

Feature: calculation-source-connectivity
Plan: `.vault/plan/2026-05-20-calculation-source-connectivity-plan.md`
Step: `W02.P04.S24` - Test profile and live source fingerprints appear in source resolution.

## Changes

- Added deterministic profile provenance fingerprints in `ProfileSourceResolver`.
- Added deterministic IVA wallet decision provenance fingerprints in `IvaWalletDecisionSourceResolver`.
- Added borrador snapshot-id fingerprints to `Modelo100BorradorSourceResolver` provenance.
- Extended `test_source_mesh_profile_live.py` to assert profile and live IVA wallet fingerprints through real source resolutions.

## Verification

- `uv run ruff check src/aeat/application/aggregation/_source_profile.py src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/modelo/_borrador_binding.py`
- `uv run pytest src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_borrador_binding.py -q --tb=short`

## Notes

- An initial focused run failed because the registry authority did not see deadline application links for Modelo 100 revisions 2023 and 2025. The current filesystem contains untracked deadline-link fragments and a fresh authority load sees the `deadline` surface; the rerun passed.
- Fingerprint assertions use real payload hashing, not test-only marker strings.
