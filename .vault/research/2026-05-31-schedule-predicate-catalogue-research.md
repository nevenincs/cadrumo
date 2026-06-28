---
tags:
  - '#research'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# schedule-predicate-catalogue research

Investigation.

The 22 predicates:

    bienes_extranjero_above_threshold
    does_intracomunitario
    enrollment.large_company
    enrollment.public_administration_budget_gt_6000000
    has_employees
    iva.intracommunity_operations_exceed_50000_eur
    iva.oss_enrolled
    iva.redeme_enrolled
    iva.regime
    iva.roi_enrolled
    iva.sii_enrolled
    irpf.estimation_regime
    irpf.special_regime
    pays_capital_income_with_retencion
    pays_professionals_with_retencion
    pays_rent_with_retencion
    professional_income_withholding_ge_70pct
    taxpayer.entity_type
    taxpayer.fiscal_residency
    taxpayer.irpf_income_categories
    third_party_transactions_above_347_threshold
    uses_objective_estimation_irpf

All 22 are declared as schedule_predicates and resolve cleanly.

### Gaps

Gap 1: Lazy not eager. ValidatedRegistryAuthority.load() does not call validate_registry().
Gap 2: Missing proof tests for filing_schedule and deadline_window surfaces.
Gap 3: Runtime alias shims in _resolve_profile_fact bypass dot-traversal for object facts.

### Validation call chain

    ValidatedRegistryAuthority.snapshot(modelo_id, ...)
      validate_modelo(modelo_id)
        RegistryValidator.validate_modelo(modelo)
          _validate_user_profile_contract((modelo,))
              validate_user_profile_registry_contract(modelos, schema)
                _schedule_issues / _deadline_issues / _cross_reference_applicability_issues

### Scope of changes

1. Add validate_registry() in _load_authority after modelos loaded.
2. Add proof tests for filing_schedule and deadline_window in test_filing_schedule_selection.py.
3. Document the two alias shims in _schedules.py inline.

### Key file locations

- src/aeat/domain/user_profile/_registry_contract.py
- src/aeat/domain/calculations/registry/_validate.py
- src/aeat/domain/calculations/registry/_schedules.py
- src/aeat/domain/calculations/registry/_authority.py
- src/aeat/_data/registry/aeat/user_profile/schema.toml
- src/aeat/domain/calculations/registry/test_cross_reference_applicability.py
- src/aeat/domain/user_profile/test_registry_contract.py
