---
tags:
  - '#exec'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:fdaca071b0adef697b79347e0014d5565dc5afe0a0916e2d23578654b6f26328'
related:
  - "[[2026-11-08-prior-carry-attestation-plan]]"
---

# `prior-carry-attestation` ledger

## Changes

- `S01` `M` `src/cadrumo/application/modelo/calculate_input.py`
- `S01` `M` `src/cadrumo/application/modelo/calculation_bucket_actions.py`
- `S01` `M` `src/cadrumo/application/modelo/calculation_helpers.py`
- `S01` `M` `src/cadrumo/application/modelo/calculation_operation.py`
- `S01` `M` `src/cadrumo/application/modelo/caller_context.py`
- `S01` `M` `src/cadrumo/application/modelo/edit_admission.py`
- `S01` `M` `src/cadrumo/application/modelo/edit_execution.py`
- `S01` `M` `src/cadrumo/application/modelo/edit_models.py`
- `S01` `M` `src/cadrumo/domain/modelos/calculation_revision_operator_layer.py`
- `S01` `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_operator_layer.py`
- `S01` `A` `src/cadrumo/entrypoints/tests/profile_persistence/test_m100_carry_attestation.py`
- `S01` `verify:` `pytest-test_m100_carry_attestation` -> `pass`
- `S01` `verify:` `pytest-test_calculation_revision_operator_layer` -> `pass`
- `S02` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_m100_carry_attestation.py`
- `S02` `verify:` `pytest-test_m100_carry_attestation` -> `pass`
- `S03` `A` `src/cadrumo/application/modelo/work_form_carry_attestation.py`
- `S03` `M` `src/cadrumo/application/modelo/work_form_models.py`
- `S03` `M` `src/cadrumo/application/modelo/work_form.py`
- `S03` `M` `src/cadrumo/application/modelo/workbench_projection.py`
- `S03` `M` `src/cadrumo/locales/ca/application.yml`
- `S03` `M` `src/cadrumo/locales/en/application.yml`
- `S03` `M` `src/cadrumo/locales/es/application.yml`
- `S03` `M` `src/cadrumo/locales/hu/application.yml`
- `S03` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S03` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_m100_carry_attestation.py`
- `S03` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S03` `M` `dev/quality/metadata/import_load_targets.json`
- `S03` `verify:` `pytest-test_m100_carry_attestation` -> `pass`
- `S03` `verify:` `check-operation-contract-manifest` -> `pass`
- `S04` `M` `native/desktop/frontend/src/components/modelo/form/session.ts`
- `S04` `M` `native/desktop/frontend/src/components/modelo/form/stagedWords.ts`
- `S04` `M` `native/desktop/frontend/src/components/modelo/form/FormView.tsx`
- `S04` `M` `native/desktop/frontend/src/components/modelo/dialogs/ReviewDialog.tsx`
- `S04` `M` `native/desktop/frontend/src/shell/modeloContract/modeloEditWork.ts`
- `S04` `M` `native/desktop/frontend/src/shell/modeloContract/modeloWorkForm.ts`
- `S04` `M` `native/desktop/frontend/tests/modelo-form-model.spec.ts`
- `S04` `verify:` `tsc` -> `pass`
- `S05` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S05` `M` `native/desktop/frontend/src/shell/modeloContract/modeloWorkForm.ts`
- `S05` `verify:` `check-operation-contract-manifest` -> `pass`
- `S05` `verify:` `pytest-test_m100_carry_attestation-every-envelope-year` -> `pass`

## Notes

- `S01` 18-failures-in-payer-fact-and-cli-calculate-suites-reproduce-on-feature/tui-HEAD
- `S02` `no-production-change:-existing-caller-tier-precedence-screen-raises-precedence_tier_divergence;-attested-mark-lives-on-the-operator-layer,-caller-provenance-stays-operator-entry`
- `S03` dev/locales/tests-spelling,hungarian-dictionary,aeat-script-cases-need-root-dictionaries-and-installed-script
- `S04` playwright-modelo-form-model-spec-runs-in-root-at-landing
