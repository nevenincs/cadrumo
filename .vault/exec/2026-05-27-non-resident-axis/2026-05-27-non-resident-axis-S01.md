---
step_id: "S01"
tags:
  - "#exec"
  - "#non-resident-axis"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-plan]]"
---

# non-resident-axis S01 — FiscalResidency + country_of_fiscal_residence + ue_eee_status

## Outcome

Task #197 complete. Non-resident taxpayer axis added as a foundational layer for
IRNR coverage (Olivia round-16). All 30 tests in TestNonResidentAxis + pre-existing
suite pass. Commit: 85a6f6dea.

## Changes

- `src/aeat/domain/profile/_renta_codes.py` — `FiscalResidency` StrEnum
  (RESIDENT_IRPF / NON_RESIDENT_IRNR) + `UE_EEA_COUNTRY_CODES` frozenset
  (EU27 + EEA, GB excluded post-Brexit 2020-12-31).

- `src/aeat/domain/deadlines/_models.py` — `TaxpayerProfile` gains
  `fiscal_residency: FiscalResidency | None`, `country_of_fiscal_residence: str | None`,
  `_check_non_resident_requires_country` model_validator (TRLIRNR RDLeg 5/2004 Art. 2),
  `ue_eee_status` computed property.

- `src/aeat/domain/deadlines/_profiles.py` — `_resolve_fiscal_residency` + `_coerce_country_code`
  helpers; both wired into `taxpayer_profile_from_mapping`.

- `src/aeat/application/wizard/_setup_answers.py` — `fiscal_residency` + `country_of_fiscal_residence`
  fields + `_parse_fiscal_residency` field validator.

- `src/aeat/application/wizard/_catalogue.py` — `_FISCAL_RESIDENCY_CHOICES`, `_NON_RESIDENT_IRNR`
  condition, two new questions in `_RESIDENCE_SECTION` (fiscal-residency SELECT before
  tax-residence-ccaa; country-of-fiscal-residence TEXT with visible_when).

- `src/aeat/application/wizard/_commands.py` — `_FISCAL_RESIDENCY_CHOICE_VALUES` + two entries
  in `_SETUP_OPTION_INFOS` (`--fiscal-residency`, `--country-of-fiscal-residence`).

- `src/aeat/domain/deadlines/__init__.py` — `FiscalResidency` added to public exports.

- `src/aeat/domain/deadlines/test_taxpayer_model.py` — `TestNonResidentAxis` (7 tests):
  validator rejection, happy path, ue_eee_status (FR=True, GB=False, None=False),
  JSON roundtrip equality, anti-tautology proof.

## Gates

- ruff: all checks passed
- pyright: pre-existing errors only (lines 108-118 in _profiles.py; not introduced here)
- pytest test_taxpayer_model.py: 30/30 passed
