---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S15'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Verify all three art-106 reglas (100/0/common) and the +10% comparison against an AEAT Manual practico worked example with no substrate-derived expected values

## Scope

- `src/aeat/application/aggregation/tests/`

## Description

- Add `src/aeat/application/aggregation/tests/test_prorrata_especial_art106_oracle.py`, a dedicated verification of the LIVA art. 106 per-input routing (S12) and the art. 103.Dos.2 +10% advisory (S13) driven end-to-end through the PRODUCTION aggregation path (`aggregate_iva_ledger_observations_from_repositories` + `resolve_iva_ledger_binding_values`).
- Verify all three art. 106.Uno reglas both composed (regla 1.ª full + regla 2.ª nil + regla 3.ª general%) and isolated per-classification, each proven distinct from the general-regime flat-percentage result.
- Verify the +10% mandatory-especial advisory fires on the REAL production general-vs-especial deducible cuota totals for the same ejercicio, and stays silent when the general deduction does not exceed the especial one.

## Outcome

The especial routing and the +10% obligation are verified against a hand-constructed register and ledger scenario driven through the production path, with a structural anti-tautology core: the especial deducible cuota (16.80) must differ from the general flat result (18.90), so a silent fallback to the general percentage would fail the test. 5 verification tests pass.

## Notes

- NO bundled AEAT *Manual práctico IVA* prorrata-ESPECIAL worked-example oracle ships in the corpus (only the general-prorrata regularización oracle `modelo-303-prorrata-general-regularizacion.json` exists). Stated explicitly in the test module docstring; per the prorrata-especial ADR this verification uses the hand-constructed-register alternative with structural anti-tautology (mirroring the art-105.Cinco global-vs-average S09 test). Expected values derive from the LIVA art. 106.Uno reglas (grounded verbatim in the bundled corpus by S10) and the chosen register percentage, never from the `deductible_percentage_for` substrate under test.
- Pre-existing peer-owned failures unrelated to this step: the import-hygiene gate reports 13 test-only `aeat.tests._inventory` reaches in concurrently-staged PEER test files (documented test-debt drift), and the bienes-inversión `casilla-63` registry-completeness broken-HEAD persists; neither references this step's files.
- Campaign-close reconciliation (W04.P05.S26): the plan Verification "Oracle grounding" bullet is amended to state especial is proven by a law-derived scenario through the production path (no bundled AEAT especial oracle), so the plan claim now matches what this step shipped. The W04.P05.S25 anti-dormant proof additionally drives the same routing through the operator `ProrrataRegisterService`.
