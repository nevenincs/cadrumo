---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S429'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Consolidate typed IVA filing-period ordering used by compensation carry-forward, IVA-wallet seeding, and filed-observation history while preserving the business rule that ranks annual 0A after periodic rows

## Scope

- `src/aeat/domain/iva_compensation/ src/aeat/application/modelo/ src/aeat/application/live/ src/aeat/**/tests/`

## Description

- Ground the change with `vaultspec-rag`, then read the full IVA carry-forward owner, IVA-wallet seed facade, filed-observation persistence surface, and their real behavior tests.
- Make the IVA-domain period-order policy consume typed `Period` classification and ordinals while retaining the policy-specific `0A` annual-after-periodic rank.
- Remove the duplicate seed-period parser and route sealed-basis ordering through the IVA domain policy.
- Route Modelo 303 filed-observation persistence, strict IVA compensation history, and latest declaration ordering through the same policy while preserving generic non-IVA numeric quarter/month and annual-last ordering.
- Add independent FIFO annual-order, real register annual-order, and encrypted-store sealed-basis immutability coverage.

## Outcome

IVA compensation period order now has one typed domain authority. Annual `0A` remains after the periodic filing rows even though its calendar span begins in January, so carry partitioning and Modelo 303 filed-history processing cannot silently fall back to generic date or token order. Non-IVA filed history retains its previous numeric quarter/month ordering and annual-last fallback. The IVA wallet correction guard continues to preserve a seeded balance once a real sealed Modelo 303 filing has consumed it. No fake, mock, stub, patch, or monkeypatch was used.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/iva_compensation/_carry_forward.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/calculations/tests/test_iva_compensation_annual_summary.py src/aeat/application/modelo/tests/test_iva_wallet_correction.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py`
- `uv run --no-sync pytest src/aeat/application/calculations/tests/test_iva_compensation_annual_summary.py src/aeat/application/modelo/tests/test_iva_wallet_correction.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q` — 41 passed.
- `uv run --no-sync pytest src/aeat/application/calculations/tests/test_iva_compensation_filed_observations.py -q` — 10 passed.
- Independent review approved the typed IVA ordering contract, all consumer migrations, and the real annual-order and sealed-basis immutability coverage.
- Review remediation: `uv run --no-sync pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/tests/test_iva_compensation_annual_summary.py src/aeat/application/modelo/tests/test_iva_wallet_correction.py src/aeat/application/calculations/tests/test_iva_compensation_filed_observations.py -q` — 52 passed; scoped Ruff clean.
- Independent re-review approved the restored non-IVA numeric ordering and the mixed real-model regression.

## Notes

The initial annual immutability case was discarded: a real Modelo 303 `0A` filing is invalid because no bundled registry revision covers it. The final immutability test instead uses a real sealed 4T Modelo 303 revision; the annual-after-periodic policy is independently exercised through the typed IVA domain and a real Modelo 390 `0A` register declaration. Independent review then caught a non-IVA generic-history ordering regression; the approved follow-up restores the original numeric `1T`, `2T`, `10`, `0A` order beside the IVA control. The plan checkbox is intentionally unchanged pending coordinated reconciliation.
