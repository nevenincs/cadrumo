---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S415'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# all-modelo-profile-binding-contract-validation

## Scope

- `src/aeat/_data/registry/aeat/modelos/ src/aeat/application/modelo/_profile_binding.py`

## Description

- Grounded the complete profile-source surface with code search and the real `validate_user_profile_registry_contract` implementation.
- Verified the discovered Modelos 036, 100, 200, 202, 210, and 303 use supported canonical `profile_key` or schema-declared `profile_model` selector forms.
- Found that the resolver projected only formula-consumed and bound-numeric profile bindings, leaving Modelo 036's typed censo event and Modelo 202's calculation-only INCN selector absent from the source mesh.
- Repaired the canonical selector boundary: bindings without XSD, XML-attribute, or dictionary export addressing are calculation inputs; export-layout identity bindings remain excluded. A calculation-only typed enum routes through the enum channel.
- Added a real `ProfileSourceResolver` regression over Modelo 036; Modelo 100 revisions 2020 through 2025; and Modelos 200, 202, 210, and 303. Each case asserts the registry binding value and its profile provenance row.
- Ran `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_source_mesh_profile_live.py src/aeat/application/modelo/tests/test_profile_binding_real_path.py src/aeat/domain/user_profile/tests/test_registry_contract.py -q`: 32 passed.
- Ran `uv run --no-sync pytest src/aeat/application/modelo/tests/test_profile_binding.py src/aeat/application/modelo/tests/test_modelo_202_sociedades_fold_in_live.py src/aeat/application/calculations/tests/test_modelo_036_censal_continuity.py src/aeat/application/modelo/tests/test_state_attribution_ratio.py -q`: 29 passed.
- Ran `uv run --no-sync ruff check src/aeat/application/modelo/_profile_binding.py src/aeat/application/aggregation/_source_profile.py src/aeat/application/aggregation/tests/test_source_mesh_profile_live.py`: passed.
- Independent `vaultspec-code-review` approved the correction with no findings.

## Outcome

Every currently registered profile-sourced binding resolves to a user-profile schema selector and its calculation-relevant values now reach the live source mesh. Modelo 036's event enum and Modelo 202's INCN source are no longer silently excluded; export-only identity bindings remain outside calculation channels.

## Notes

This validation covers the present registry surface; a future modelo with a profile source remains protected by the all-modelo schema-contract test and the explicitly enumerated resolver smoke cases require a review when the surface changes.
