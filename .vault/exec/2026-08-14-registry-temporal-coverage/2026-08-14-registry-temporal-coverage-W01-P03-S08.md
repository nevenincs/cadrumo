---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:6f908c366d015803f81be6332599f2933bc83e4c0932b88c4868ce4fdb859bd5'
step_id: 'S08'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Declare the applicability fragment family in the registry schema, loader and build validation so a modelo obligation rule hydrates from authoring-tree TOML through the authority

## Scope

- `src/cadrumo/domain/calculations/registry/ids.py`
- `src/cadrumo/domain/calculations/registry/schema.py`
- `src/cadrumo/domain/calculations/registry/loader.py`
- `src/cadrumo/domain/calculations/registry/applicability.py`
- `src/cadrumo/domain/calculations/registry/_validate_applicability_section.py`
- `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py`
- `src/cadrumo/domain/calculations/registry/tests/test_applicability_fragment_family.py`
- `src/cadrumo/domain/calculations/registry/tests/test_applicability_registry_cutover.py`

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

The production family landed in commit `a16b0b8ffd` and remains canonical after the public-module relocations. Current isolated verification passed all six fragment-family tests, covering schema enrollment, fragmented TOML loading, inline-manifest refusal, typed hydration, unknown-token naming, and accumulated validation failures. The three scratch-tree authority-cutover tests also passed, proving real `ValidatedRegistryAuthority.load`, result equivalence, nonuniform verdicts, and fresh-authority mutation visibility. Terra's broader focused schema/loader/validator/grade selection passed 36/36; commit `14e3d2d744` corrected only relocated test import ordering. Ruff format/check and `git diff --check` passed.

These temp-tree proofs are the current acceptance evidence. The historical 2,751 bundled-tree failures recorded during the original campaign are not treated as evidence of present whole-tree health.

## Notes

The applicability family intentionally does not create a second snapshot projection: applicability is resolved at the authority scheduling boundary, below filing-grade snapshot admission. The typed authoring definition, hydration boundary, and validator remain single-owned.

No production residue or Modelo 200 path was touched during this reconciliation.
