---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:54f2c5569662d46216bb0c24c832dbb07ac87e4c82ccf01e53afd29139332205'
step_id: 'S61'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Move arrendamiento_vivienda_afecto from PREMISES into HOME_OFFICE_OWNERSHIP as the renter's parallel to amortizacion/ibi/comunidad_vivienda_afecto, correcting its citation from the suministros-only art. 30.2.5.b to the general art. 29.2 partial-affectation doctrine plus art. 28.1, and dropping its stray default_ratio so it now requires an explicit operator ratio like its true siblings

## Scope

- `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`
- `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`
- `src/cadrumo/domain/categories/_spending_category.py`

## Description

- Move `SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO` from the `PREMISES` family into `HOME_OFFICE_OWNERSHIP` in `CATEGORY_FAMILY_MEMBERS`, alongside its true economic siblings `amortizacion_vivienda_afecto` / `ibi_vivienda_afecto` / `comunidad_vivienda_afecto`.
- Correct its citations in both 2024.toml and 2025.toml: drop the unsupported art. 30.2.5.b (a suministros-only carve-out that does not enumerate rent), replace with a ley_irpf citation to art. 29.2 (general partial-affectation doctrine) plus art. 28.1 (general deductibility), and rename the manual_renta locator to "Vivienda parcialmente afecta - arrendamiento" matching the sibling naming convention.
- Drop the stray `default_ratio = "0.30"` its true siblings do not carry -- it was a registry-supplied fabricated default (no legal basis, and it happened to equal the unrelated suministros-only figure) rather than a display convenience.
- Translate the corrected `categories.registry.arrendamiento_vivienda_afecto.notes` leaf across all four locale catalogues via `python -m cadrumo.locales set`, removing the "(ratio por defecto 30%)" phrasing and citing art. 29.2 + art. 28.1.
- Add anti-tautology pins: a concrete-value test asserting arrendamiento derives to the raw ratio (parity with `ibi_vivienda_afecto`, never the suministros-multiplied figure), and two censo-guard tests (refuse-on-unconsented-override, accept-on-censo-matching-value).
- Fix a real regression the family move surfaced: `test_usage_ratio_default_splits_deductible_and_non_deductible_amounts` asserted ELIGIBLE with `applied_ratio == 0.30` from the registry `default_ratio` fallback with no operator-set usage ratio at all -- that assumption was the bug under test. Replaced it with `test_arrendamiento_vivienda_afecto_is_ineligible_until_user_ratio_exists`, a paired test (missing/with_ratio) mirroring the existing `TELEFONIA_MOVIL` pattern: INELIGIBLE ("missing usage ratio") with no context ratio, ELIGIBLE once the operator supplies one explicitly.
- Recorded the `HOME_OFFICE_OWNERSHIP` misnomer (the family now holds a non-ownership, rental member) as a named code comment rather than renaming the family -- per instruction, the correctness fix should not wait behind a rename that touches every consumer of the family constant.

## Outcome

`arrendamiento_vivienda_afecto` (the renter's parallel to the three vivienda_afecto ownership costs) previously sat in `PREMISES` -- grouped with `arrendamiento_local`, a dedicated-commercial-premises rent it has nothing in common with -- and cited art. 30.2.5.b, a provision that verbatim enumerates only "agua, gas, electricidad, telefonía e Internet" and says nothing about rent. Sitting outside `HOME_OFFICE_OWNERSHIP` meant it was neither auto-derived from the operator's censo declaration nor covered by the censo-consistency guard, so an operator (or a bug) could persist any ratio for it with zero cross-check -- the same defect class the guard exists to close for its true siblings. It also carried a `default_ratio = "0.30"` with no legal basis, which silently granted a 30% deduction on rent with **zero operator input at all** via the `evaluate_renta_deductibility` fallback (`context.usage_ratios.get(fact.category, rule.default_ratio)`) -- a genuine additional finding surfaced only once the family move exposed the existing test's premise as wrong.

It now derives at the raw affectación ratio (no statutory multiplier, matching its true ownership siblings), is auto-populated by the censo-derivation service, is blocked by the censo-consistency guard on any operator override that disagrees with the bound censo, and requires an explicit operator-set ratio before it is eligible at all -- it no longer grants a deduction from a fabricated registry default.

The `HOME_OFFICE_OWNERSHIP` family name is now a minor misnomer (it holds a rental cost alongside three ownership costs); this is recorded as a code comment naming a future rename to something like `HOME_OFFICE_DWELLING_COST`, deferred so the correctness fix does not wait behind a broader consumer sweep.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/usage_ratios src/cadrumo/domain/categories src/cadrumo/domain/renta src/cadrumo/domain/transactions -n 0 -q --no-header
    335 passed in 17.73s

    uv run --no-sync pytest src/cadrumo/domain/categories/tests/test_citation_authority.py -n 0 -q --no-header
    9 passed in 0.76s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py -m integration -n 0 -q --no-header
    26 passed in 16.35s

    uv run --no-sync python -m cadrumo.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Mutation proof (family-membership axis): reverted `ARRENDAMIENTO_VIVIENDA_AFECTO` from `HOME_OFFICE_OWNERSHIP` back into `PREMISES`; `test_arrendamiento_vivienda_afecto_concrete_value_at_20_percent_afectacion` (KeyError: no longer derived) and `test_refuses_when_censo_unset_but_arrendamiento_vivienda_afecto_override_persisted` (DID NOT RAISE) reddened, while the family-independent tests (`test_derivation_covers_every_home_office_category`, `test_ownership_categories_apply_raw_afectacion_with_no_multiplier`) stayed green. Restored from a pre-mutation backup; sha256 confirmed byte-identical before and after.

Mutation proof (default_ratio axis): re-added `default_ratio = "0.30"` to `arrendamiento_vivienda_afecto` in both TOMLs; `test_arrendamiento_vivienda_afecto_is_ineligible_until_user_ratio_exists`'s `missing.status is INELIGIBLE` assertion reddened (the fallback made it ELIGIBLE again with no operator input). Restored from a pre-mutation backup; sha256 confirmed byte-identical before and after.

## Notes

Related, out-of-scope finding: `amortizacion_vivienda_afecto` / `ibi_vivienda_afecto` / `comunidad_vivienda_afecto` -- the true `HOME_OFFICE_OWNERSHIP` siblings -- ALSO cite art. 30.2.5.b in both years, each with a fabricated parenthetical "(regla N.a, ...)" label that does not match the real numbered reglas in the bundled LIRPF text (regla 2.a governs cónyuge/hijos menores wages, regla 4.a governs the estimación directa simplificada 2.000-euro cap; neither discusses vivienda-ownership costs). Their citations were left untouched in this Step -- only `arrendamiento_vivienda_afecto`'s were in scope -- but the same wrong-provision defect class now applies to all three of its true siblings and is worth a follow-up sweep.
