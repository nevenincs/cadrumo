---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
  - "[[2026-05-27-cross-domain-continuity-w09-p41-s176-review-exec]]"
---

# cross-domain-continuity Code Review

Commit 85a6f6dea -- #197 non-resident taxpayer axis: FiscalResidency + country_of_fiscal_residence + ue_eee_status

**Verdict: REVISION REQUIRED**

---

## WIZARD-001 | CRITICAL | irpf-special-regime and irpf-special-regime-start-date missing from _SETUP_OPTION_INFOS -- CLI crashes on command registration

This commit adds two new WizardQuestion entries to _OBLIGATIONS_SECTION in _catalogue.py with IDs irpf-special-regime and irpf-special-regime-start-date. The _python_parameter dispatch loop at _commands.py line 454 does _SETUP_OPTION_INFOS[question.id] with no guard -- a missing key raises KeyError at CLI command registration time, before any command can run. Both new IDs are absent from _SETUP_OPTION_INFOS. Parity check confirmed at runtime: Missing = [irpf-special-regime, irpf-special-regime-start-date]. situacion-familiar was already missing before this commit (pre-existing debt) and is out of scope here, but the two new IDs are a regression introduced by this commit. Fix: add typer.Option entries for both keys to _SETUP_OPTION_INFOS in _commands.py.

---

## LOCALE-001 | HIGH | All fiscal-residency and country-of-fiscal-residence locale keys absent from all 4 locale files

The catalogue references tr(wizard.setup.residence.fiscal-residency.prompt), the choice labels, tr(wizard.setup.residence.country-of-fiscal-residence.prompt), and _SETUP_OPTION_INFOS references tr(wizard.setup.flags.fiscal-residency.help) and tr(wizard.setup.flags.country-of-fiscal-residence.help). None of these keys exist in es.yml, en.yml, ca.yml, or hu.yml. At runtime they silently fall back to capitalised key stems (Prompt, Help), producing nonsense operator output. G3 + G4 violation. Fix: run python -m aeat.locales scaffold then provide substantive translations in all 4 languages.

---

## COUNTRY-001 | HIGH | UE_EEA_COUNTRY_CODES uses Eurostat code EL for Greece instead of ISO 3166-1 alpha-2 GR

country_of_fiscal_residence is documented as ISO 3166-1 alpha-2. Any Greek resident who supplies GR (the correct ISO code) gets ue_eee_status = False, misclassifying an EU member as non-EU. EL is the EU/Eurostat statistical code, not the ISO 3166-1 code for Greece (GR). Fix: replace EL with GR in UE_EEA_COUNTRY_CODES in src/aeat/domain/profile/_renta_codes.py and update the source comment to cite the ISO 3166-1 MA list as authority.

---

## CCAA-001 | HIGH | CCAA wizard question has no visible_when suppression for NON_RESIDENT_IRNR

The tax-residence-ccaa question in _RESIDENCE_SECTION carries no visible_when condition -- it is always shown and defaults to Madrid. Per spec (Lourdes F8 / Olivia round-16), CCAA must be suppressed (not silently defaulted) when fiscal_residency = NON_RESIDENT_IRNR. Fix: add a visible_when condition hiding tax-residence-ccaa for non_resident_irnr. Also verify taxpayer_profile_from_mapping does not copy tax_residence_ccaa for non-resident profiles.

---

## COUNTRY-002 | MEDIUM | No format validator for country_of_fiscal_residence in TaxpayerProfile

The field is documented as ISO 3166-1 alpha-2 (2-letter uppercase), but TaxpayerProfile has no field_validator enforcing this. A 3-character code or arbitrary string is accepted silently. _coerce_country_code only upper-cases and strips. Add a field_validator asserting len == 2 and alpha-only (post-normalisation) to surface bad input at the domain boundary.

---

## M100-001 | FU | M100 IRPF refusal for NON_RESIDENT_IRNR not wired

Per spec, M100 must refuse for fiscal_residency = NON_RESIDENT_IRNR (parallel to foral CCAA refusal #175). No such guard exists in overview, diagnostics, or CLI layers. File as a follow-up task.

---

## Critical Question Answers

**Q1 -- model_validator:** IMPLEMENTED. _check_non_resident_requires_country rejects NON_RESIDENT_IRNR without country. The RESIDENT_IRPF inverse (country must be None when resident) is not enforced -- minor gap.

**Q2 -- ue_eee_status:** Implemented as property using UE_EEA_COUNTRY_CODES. GB correctly excluded. EL/GR mismatch breaks Greece classification -- see COUNTRY-001.

**Q3 -- CCAA suppression:** NOT implemented. Wizard question always visible; non-residents default to Madrid. See CCAA-001.

**Q4 -- CLI flags:** PASS. Both --fiscal-residency (click.Choice) and --country-of-fiscal-residence (bare str) are in _SETUP_OPTION_INFOS and catalogue.

**Q5 -- _SETUP_OPTION_INFOS parity (#228 family):** FAIL. irpf-special-regime and irpf-special-regime-start-date added to catalogue but absent from _SETUP_OPTION_INFOS. CLI-crash regression. See WIZARD-001.

**Q6 -- Locale parity:** PARTIAL FAIL. irpf-special-regime keys exist with substantive translations in all 4 locales. fiscal-residency and country-of-fiscal-residence keys entirely absent from all 4 locales. See LOCALE-001.

**Q7 -- Roundtrip + anti-tautology:** PASS. TestNonResidentAxis provides JSON roundtrip test and anti-tautology proof (drop country -> ValidationError). Real-behavior, no mocks.

**Q8 -- M100 refusal:** NOT wired. See M100-001 FU.
