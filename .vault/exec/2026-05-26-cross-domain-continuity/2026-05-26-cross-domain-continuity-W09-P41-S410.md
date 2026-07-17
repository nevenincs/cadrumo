---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S410'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# verify Modelo 202 2025-3P payment_cutoff_on against the year-specific AEAT calendar and decide whether direct-debit cutoffs shift independently from the general day-15 rule

## Scope

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/`

## Description

- Ground the cutoff question with `uvx vaultspec-rag search "Modelo 202 2025 3P payment_cutoff_on domiciliation December 2025 direct debit cutoff" --type code`.
- Correct `modelo-202-2025-3p` from `payment_cutoff_on = 2025-12-15` to `payment_cutoff_on = 2025-12-17`.
- Add a committed-registry regression test for Modelo 202 2025 `2P` and `3P` opening, closing, and direct-debit cutoff dates.
- Resolve review provenance feedback by adding `aeat-calendario-contribuyente-2025` to the source catalogue, bundling the official AEAT 2025 contributor calendar PDF, and citing that source from the 2025 `3P` deadline window.

## Outcome
- Modelo 202 2025 `3P` now follows the year-specific AEAT calendar: filing opens `2025-12-01`, closes `2025-12-22`, and direct debit remains available through `2025-12-17`.
- The 2025 `2P` baseline remains unchanged: filing opens `2025-10-01`, closes `2025-10-20`, and direct debit remains available through `2025-10-15`.
- The corrected shifted cutoff is now traceable through a real source reference, `aeat-calendario-contribuyente-2025`, backed by bundled corpus bytes.
- The new source corpus fingerprint was verified at `2206696` bytes and SHA-256 `dfdcae8889ab5fecffa368e235d933676c8a479915e09b107734f8339eed0f50`.

## Notes

- Focused validation passed: `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_202_deadline_windows.py src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py -q -p no:cacheprovider` returned `21 passed`.
- Lint passed: `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_202_deadline_windows.py`.
- Source-resolution and fingerprint validation passed through the real registry loader and `RegistryValidator`.
- Plan validation passed with the existing `PLAN022` non-monotonic canonical-id warning only.
- A broad registry coherence run by the provenance worker hit unrelated Modelo 100 revision 2024 errors in the shared worktree; focused Modelo 202 validation and source fingerprint checks did not reproduce an S410 defect.
