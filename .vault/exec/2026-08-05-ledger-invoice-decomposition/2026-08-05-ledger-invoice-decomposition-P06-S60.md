---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:d8582c9f27397c25631aa148be294534e5e8afd63b27372167d457eaefeba84e'
step_id: 'S60'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Reground telefonia_fija to LIRPF art. 30.2.5.b's own suministros enumeration (agua, gas, electricidad, telefonia e Internet), moving it into HOME_OFFICE_SUMINISTROS with the statutory 0.30 multiplier it was missing, since it previously deducted at the raw home-area ratio with no censo-consistency guard

## Scope

- `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`
- `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`
- `src/cadrumo/domain/categories/_spending_category.py`

## Description

- Add a `statutory_multiplier = "0.30"` to `telefonia_fija`'s proportionality rule in both the 2024 and 2025 category profile TOMLs, so it applies the same LIRPF art. 30.2.5.b (regla 5.ª b) 30% carve-out its four `suministros_home_office_*` siblings already carry, instead of the raw `default_ratio` alone.
- Re-ground `telefonia_fija`'s citations on the same provision as its statutory siblings (art. 30.2.5.b, which enumerates "agua, gas, electricidad, telefonía e Internet" together), dropping the unsupported bare art. 28.1 pairing.
- Move `SpendingCategory.TELEFONIA_FIJA` from the `TELECOMS` family into `HOME_OFFICE_SUMINISTROS` in `CATEGORY_FAMILY_MEMBERS`, so it is now covered by the same censo-derivation (`derive_home_office_ratios_from_censo`) and censo-consistency guard (`load_usage_ratios_with_censo_guard`) as its four statutory siblings, per the family-keyed invariant.
- Translate the new `categories.registry.telefonia_fija.notes` leaf across all four locale catalogues via `python -m cadrumo.locales set`, matching its statutory sibling's wording verbatim per language.
- Add anti-tautology pins locking the corrected arithmetic and guard coverage: a concrete-value test asserting `telefonia_fija` derives to exactly the same figure as `suministros_home_office_internet` at a given afectación ratio, and two censo-guard tests (refuse-on-unconsented-override, accept-on-censo-matching-value).
- Separately, audit `ARRENDAMIENTO_VIVIENDA_AFECTO` against the same bundled LIRPF text: confirmed it is a genuinely different defect, not the same shape, and left unfixed pending an operator decision (see Notes).

## Outcome

`telefonia_fija` (a fixed telephone line at the taxpayer's partially affected vivienda habitual) previously deducted at the raw home-area ratio with no statutory multiplier and no censo-consistency guard: an operator with 20% home-office afectación deducted 20% of their landline bill instead of the legally correct 6% (20% × 30%), a roughly 3.3x overstatement, and could freely override the ratio to any value with no check against their bound censo declaration. It now derives identically to its four `suministros_home_office_*` siblings under LIRPF art. 30.2.5.b, is auto-populated by the censo-derivation service, and is blocked by the censo-consistency guard on any operator override that disagrees with the bound censo.

`ARRENDAMIENTO_VIVIENDA_AFECTO` is a separate, real defect, not landed in this Step: verbatim art. 30.2.5.b (regla 5.ª b) names only "agua, gas, electricidad, telefonía e Internet" as the suministros carried at the 30% carve-out; it says nothing about rent. `arrendamiento_vivienda_afecto` nonetheless cites art. 30.2.5.b in both the 2024 and 2025 profiles, and is classified in the `PREMISES` family (alongside `arrendamiento_local`, a dedicated-commercial-premises rent) rather than in `HOME_OFFICE_OWNERSHIP` (where its true economic siblings `amortizacion_vivienda_afecto` / `ibi_vivienda_afecto` / `comunidad_vivienda_afecto` live, each with no `default_ratio` and no `statutory_multiplier` — the raw partial-affectation ratio applies directly, grounded on the general art. 29.2 partial-affectation doctrine plus art. 28.1, not on the suministros-specific regla). Because it sits outside `HOME_OFFICE_OWNERSHIP`, it is neither auto-derived from the censo nor covered by the censo-consistency guard, so an operator can persist any ratio for it with zero cross-check — the same defect class the guard exists to close for its true siblings. It also carries a `default_ratio = "0.30"` that none of its true ownership-cost siblings carry, which looks like a copy-paste artifact from the suministros pattern rather than a deliberate value (the field is CLI-display-only metadata; it has no effect on the actual deduction arithmetic).

This is not the same fix as `telefonia_fija`: `telefonia_fija` was missing a multiplier it does need; `arrendamiento_vivienda_afecto` does not need a multiplier at all (a raw-ratio, ownership-family shape is correct for it), and instead needs a family move plus a citation correction to a different article pair. Landing it also touches whether "arrendamiento_vivienda_afecto" is intended as the renter's parallel to the three ownership categories (my reading of the family split) or reflects some other intended distinction, which is outside the scope of this Step and is reported rather than fixed.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/usage_ratios src/cadrumo/domain/categories -n 0 -q --no-header
    97 passed in 6.88s

    uv run --no-sync pytest src/cadrumo/domain/categories/tests/test_citation_authority.py -n 0 -q --no-header
    9 passed in 0.86s

    uv run --no-sync python -m cadrumo.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Mutation proof (multiplier axis): removed `statutory_multiplier = "0.30"` from `telefonia_fija` in both TOMLs; `test_suministros_apply_lirpf_art_30_2_rule_5_30pct_multiplier`, `test_telefonia_fija_concrete_value_at_20_percent_afectacion`, and `test_accepts_telefonia_fija_when_persisted_matches_censo_derived_value` reddened (3 failed, 1 passed against the `-k "telefonia_fija or rule_5_30pct"` selection), while the family-membership-only control (`test_refuses_when_censo_unset_but_telefonia_fija_override_persisted`) stayed green. Restored from a pre-mutation backup; sha256 confirmed byte-identical before and after.

Mutation proof (family-membership axis): reverted `TELEFONIA_FIJA` from `HOME_OFFICE_SUMINISTROS` back into `TELECOMS` in `_spending_category.py`; `test_telefonia_fija_concrete_value_at_20_percent_afectacion` (KeyError: no longer derived) and `test_refuses_when_censo_unset_but_telefonia_fija_override_persisted` (DID NOT RAISE) reddened, while the family-independent tests (`test_derivation_covers_every_home_office_category`, `test_suministros_apply_lirpf_art_30_2_rule_5_30pct_multiplier`) stayed green. Restored from a pre-mutation backup; sha256 confirmed byte-identical before and after.

## Notes

`ARRENDAMIENTO_VIVIENDA_AFECTO`'s defect (wrong family, wrong citation, stray `default_ratio`) is real and grounded against the bundled LIRPF text, but is left as an open follow-up rather than landed in this Step, pending confirmation of whether it is intended as the renter's parallel to `HOME_OFFICE_OWNERSHIP` (this Step's working assumption) before its family and citations are corrected.
