---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d62416e237000ae1407d3099bfde2760a3199470b7ce8033810ab8173e2e5ffc'
step_id: 'S34'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Name the outstanding schema-required fields on the setup-incomplete refusal when the enumeration finds any, falling back to the existing generic wording for a cross-field-only failure, per the per-operation-axis audit's open ready-to-execute item

## Scope

- `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `src/cadrumo/locales/{en,es,ca,hu}.yml`

## Description

- New Step opened mid-loop: the governing audit records a distinct, genuinely open finding ("Open, ready to execute: the setup-incomplete refusal names no field") that was blocked only by peer file contention on `_profile_readiness_gate.py`, a file this campaign has since been actively and repeatedly editing (P06.S18, P06.S19) - the contention no longer applies, so this Step actions it in the same pass rather than leaving a ready-to-execute audit item untracked.
- In `require_profile_ready_for_modelo_work`'s `SETUP_INCOMPLETE` branch: compute `missing_required_field_paths(schema, record_to_path_values(record))` (the same shared helper `ProfileValidationService` and the overview surface already use) before refusing. When it returns at least one path, raise a NEW key `application.modelo.errors.profile_readiness_setup_incomplete_missing` naming every missing field by its catalogue label (via `build_profile_preflight_requirement(...).label`, never a raw dotted path) in a `%{missing}` context slot, mirroring the sibling `profile_readiness_missing` refusal's shape. When the enumeration is empty, kept the ORIGINAL generic `profile_readiness_setup_incomplete` wording - per the audit's own caveat, `SETUP_INCOMPLETE` also fires on a pure cross-field validation failure with every individual required field populated, and enumerating nothing there must not read as "missing: nothing".
- Added the new locale key via `dev.locales set` in all four catalogues (en/es/ca/hu) - real translations, not placeholders - then ran `scaffold` and `scaffold --check` clean.
- Exported `missing_required_field_paths` through `application/user_profile`'s facade (it was previously only used internally within the package), following the same lazy `__all__`/lazy-load-table pattern used for `build_profile_preflight_requirement` in P06.S19.

## Outcome

A genuinely-missing required field on a `SETUP_INCOMPLETE` profile is now named in the refusal; a pure cross-field failure keeps the prior generic wording. Both branches are covered by grounded regressions.

## Verification

```
uv run --no-sync python -m dev.locales scaffold --check
ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/tests/test_parity.py src/cadrumo/tests/test_locale_translation_honesty.py
41 passed in 184.94s (0:03:04)
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -m unit
22 passed in 11.07s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/ -m unit
2065 passed, 12 failed, 185 deselected in 304.81s
```

The 12 failures are the same pre-existing `NoRevisionForPeriodError`-rooted Modelo 200/202 registry-data failures recorded in P06.S18 and P06.S19's execution records, unrelated to this Step's files.

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py src/cadrumo/entrypoints/cli/tests/test_modelo_100_readiness_missing_bindings.py src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py -m integration
33 passed in 32.99s
```

## Notes

**A reasoned test scenario failed against the real entry point, exactly the pattern this campaign's governing audit warns about.** The first regression attempt drove the new branch through `create_work_unit` with a profile missing `identity.name`, reasoning that the SETUP_INCOMPLETE check would fire and name the gap. It did not: `create_work_unit` runs `require_existing_profile_baseline_ready_for_modelo_work` FIRST, an early, status-blind gate that already refuses with the generic `profile_readiness_missing` message for ANY missing required field (via `ProfileValidationService`'s error-severity issues, not just the two-path baseline tuple) - before the status-aware gate with this Step's new branch ever runs. Running the test and reading its actual failure (not the reasoned expectation) revealed this: the new branch is reachable only when a work unit ALREADY EXISTS and its profile is re-checked via `require_profile_ready_for_work_unit` (calculate/verify/export), which calls the status-aware gate directly with no earlier competing check. The test and this note were both corrected to reflect the narrower, measured reach rather than the wider, reasoned one - recorded here per the campaign's own discipline that a measured claim survives and a merely-reasoned one does not.
