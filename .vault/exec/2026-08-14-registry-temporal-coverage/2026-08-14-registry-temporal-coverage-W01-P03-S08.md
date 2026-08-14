---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:6f908c366d015803f81be6332599f2933bc83e4c0932b88c4868ce4fdb859bd5'
step_id: 'S08'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Declare the applicability fragment family in the registry schema, loader and build validation so a modelo obligation rule hydrates from authoring-tree TOML through the authority

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`
- `src/cadrumo/domain/calculations/registry/_loader.py`
- `src/cadrumo/domain/calculations/registry/_applicability.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add `ApplicabilityRuleId` to `_ids.py`, matching the existing typed-id pattern.
- Add `ApplicabilityRuleDefinition` to `_schema.py`: every closed-vocabulary field is a plain `tuple[str, ...]` (never a `domain.deadlines` enum type), because importing that package into `_schema.py` would close a real import cycle -- `domain.deadlines` itself depends on `DeadlineWindowDefinition`, declared in the same module.
- Add `applicability: Annotated[tuple[ApplicabilityRuleDefinition, ...], SCHEMA_FAMILY]` to `ModeloRevision`.
- Add `hydrate_applicability_rule(modelo, fragment)` to `_applicability.py`: the loader boundary resolving every free-form string to its real `domain.deadlines`/`PayerFact` enum member, raising `RegistryValidationError` naming the offending token on failure rather than a raw `ValueError`.
- Add `validate_applicability_section` in new `_validate_applicability_section.py`: accumulates rather than raises, preserves the underlying pydantic/enum-coercion error text, checks cardinality (at most one rule per revision) and legal-ref resolution.
- Export `ApplicabilityRuleDefinition`, `ApplicabilityRuleId`, `hydrate_applicability_rule` through the package facade.
- Loader wiring required zero manual changes: `_compute_revision_section_fields`/`_REVISION_APPEND_ARRAYS` in `_loader.py` are already fully shape-derived from `ModeloRevision`'s fields, so the fragmented-layout invariant (inline-section refusal) and directory-mode fragment merging picked up the new family automatically.
- Build-validation dispatch: `validate_applicability_section` call added to `_validate_revision_surface_sections` in `_validate_revision_sections.py`, immediately after `validate_dependency_classification_section` (landed by the coordinating agent, who owned that file; the caller passes `modelo` as a plain `str` matching the dispatcher's own convention, which required changing this Step's function signature from `Modelo` to `str` with an internal conversion).
- Add `tests/test_applicability_fragment_family.py` (6 tests): SCHEMA_FAMILY enrolment, a real fragmented-directory load, an inline-manifest-refusal anti-tautology proof, a hydration round-trip across every axis, an unknown-token-naming proof, and validator accumulate-not-raise.

## Outcome

All 6 new tests pass. Re-ran `test_schema_family_coverage.py` (23 tests) and `test_authority_grade_ladder.py` (6 tests) read-only -- both green; the new family enrolled with zero edits needed in either file, and enrolling it did not trip the grade ladder. Ran the full `RegistryValidator(catalogues, source_root=root).validate_registry(modelos)` against the real bundled tree (every modelo, every revision): 2751 pre-existing unrelated failures, zero applicability-related failures -- correct, since no revision carried the fragment yet at that point in the campaign. `ruff check` and `ruff format --check` clean on every touched file.

## Notes

Caught and fixed a real `ruff` F401 regression from this session's own earlier `W01.P04.S10`/`S34` work while editing the same file: 5 names demoted from `__all__` but left imported were unused-import violations ruff had not been run against since. Fixed with the `import X as X` redundant-alias idiom (ruff's own suggested fix), then re-confirmed the import-hygiene Family-7 gate still passes.

One incidental asymmetry surfaced and deliberately left alone: `RegistrySnapshot` carries a `Mapping[Id, Definition]` projection for every OTHER schema family (`dependency_classifications`, `constructs`, etc.) but not `applicability`. Ruled correct, not a gap, by the coordinating agent: applicability answers "is this modelo due, and to whom" -- the floor rung of the authority-grade ladder (scheduling reach) -- while `RegistrySnapshot` is a filing-context projection one rung up. Resolving applicability without filing-grade review is correct per that ladder, not a gate dodged. Recorded in `resolve_applicability_rule_from_authority`'s docstring in `_applicability.py`.
