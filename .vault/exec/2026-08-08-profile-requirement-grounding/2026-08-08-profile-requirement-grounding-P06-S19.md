---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d645c7881273448bac70acf6bdaf84d9706ce8d2916942f42e6ffb2b8495087a'
step_id: 'S19'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Merge ProfilePreflightService._requirement and _requirement_for_profile_path into one shared builder taking an optional grounding index

## Scope

- `verification gate: a parity test proving the merged builder's output is unchanged for every case the two prior functions covered`
- `src/cadrumo/application/user_profile/_preflight.py`
- `src/cadrumo/application/modelo/_profile_readiness_gate.py`

## Description

- Added `build_profile_preflight_requirement(path, *, schema, selector=None, grounding_index=None)` as a module-level function in `_preflight.py`, taking the more general shape of the two prior implementations (a single `path` string covering both a pre-split `section.field` path and a bare non-dotted validation-issue code, matching `_requirement_for_profile_path`'s wider contract) plus an explicit `schema` parameter (the injected schema instance, rather than either implementation's own fixed source).
- Deleted `ProfilePreflightService._requirement` entirely and rewrote its four call sites (the per-operation schema walk, the two export-identity branches, and the conditional-requirement branch) to call the shared function with `schema=self._schema`.
- Reduced `_profile_readiness_gate._requirement_for_profile_path` to a thin call-site wrapper delegating 100% of its logic to the shared function with `schema=resources().user_profile_schema.singleton` - kept as a named wrapper (not inlined at its three call sites) since all three already pass a bare `path` plus optional `selector`/`grounding_index`, and the wrapper carries zero independent logic, so it does not reintroduce a second implementation.
- Deleted the now-fully-absorbed `_split_profile_path` helper from `_profile_readiness_gate.py`.
- Exported `build_profile_preflight_requirement` through `application/user_profile`'s lazy `__all__`/lazy-load table (the package's established PEP 562 pattern), so the cross-package import from `application/modelo` resolves to the owning package's public facade per this project's import-centralisation rule.
- Removed now-unused imports from `_profile_readiness_gate.py` (`UserProfileNotFoundError`, `profile_field_label`, `section_field_key` from `domain.user_profile` - all absorbed into the shared builder) and confirmed with `ruff check` on all three touched files.

## Outcome

One requirement-row builder exists (`build_profile_preflight_requirement`), consumed by `ProfilePreflightService.report()`'s four call sites directly and by `_profile_readiness_gate.py`'s three call sites via a zero-logic wrapper. `ruff check` and the import-hygiene gate both pass.

## Verification

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/domain/user_profile/tests/ -m unit
632 passed, 72 deselected in 87.67s (0:01:27)
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py src/cadrumo/entrypoints/cli/tests/test_modelo_100_readiness_missing_bindings.py src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py -m integration
33 passed in 33.73s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/tests/test_import_hygiene_gate.py
19 passed in 76.44s (0:01:16)
```

The parity gate this Step requires: three existing tests in `test_services.py` called the now-deleted `svc._requirement(...)` private method directly and broke on removal - not a silent skip, they were rewritten to call `build_profile_preflight_requirement` directly with identical inputs, preserving every original assertion. A fourth, new test (`test_preflight_requirement_builder_matches_service_report_output_for_tax_id`) proves the merged builder called directly reproduces byte-for-byte (`==` on the pydantic model) the exact `ProfilePreflightRequirement` row `ProfilePreflightService.report()` itself produces for a missing `identity.tax_id` under Modelo 100 - the strict-equality case the plan step names.

A broader unit run (`src/cadrumo/application/modelo/tests/`, 2060 passed / 15 failed) showed the same 12 pre-existing `NoRevisionForPeriodError`-rooted Modelo 200/202 failures already recorded in P06.S18's execution record, unrelated to this Step's files.

## Notes

One edit mishap: the first attempt at rewriting `test_preflight_requirement_never_invents_grounding_for_unknown_path` left a stray orphaned assertion line (`assert requirement.modelos == ()`) attached to the wrong, newly-added test below it, referencing an undefined name. Caught immediately by the test run (`NameError: name 'requirement' is not defined`), not by inspection; removed in the same pass before landing.
