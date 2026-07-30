---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S44'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# carry the validated label onto the classification row and finding models so a degraded read stays labelled when its findings are flattened, implementing the ADR ruling on row-level labelling

## Scope

- `src/cadrumo/domain/calculations/registry/_classification_coherence.py`

## Description

- Read `_classification_coherence.py` and `test_classification_coherence.py` in full to identify every construction site for `ClassificationCoherenceFinding` and `ModeloClassificationRow`.
- Verified no peer WIP on both files via `git diff -- <file>`.
- Added `registry_validated: bool` field to `ClassificationCoherenceFinding` with a docstring explaining that the flag mirrors the audit-level stamp down onto each finding so the label survives flattening through `RegistryClassificationAudit.findings`.
- Added `registry_validated: bool` field to `ModeloClassificationRow` with a docstring explaining the same rationale for row-iterating consumers.
- Updated `build_classification_coherence_audit` to pass `registry_validated` to `_build_row`.
- Updated `_build_row` to accept `registry_validated` and thread it to: `_informative_divergence_finding`, both inline `ClassificationCoherenceFinding` constructions (`non_registry_modelo_defined_in_tree`, `registry_modelo_absent_from_modelo_enum`), `_dependency_findings`, and the `ModeloClassificationRow` constructor.
- Updated `_informative_divergence_finding` to accept `registry_validated` and pass it to its `ClassificationCoherenceFinding` construction.
- Updated `_dependency_findings` to accept `registry_validated` and pass it to each `ClassificationCoherenceFinding` it constructs.
- Added `registry_validated=False` to the two test sites that directly construct `ClassificationCoherenceFinding` (`test_the_detail_bound_is_read_from_the_field_it_must_satisfy`, `test_the_clamp_is_what_keeps_an_oversized_detail_constructible`).
- Added `test_degraded_read_stamps_every_row_and_finding_unvalidated`: a non-validating read with a divergent modelo asserts every row and every finding carries `registry_validated=False`.
- Added `test_validated_read_stamps_every_row_and_finding_validated`: a validated read with the same modelo asserts every row and finding carries `registry_validated=True` (anti-tautology pair).
- Added `test_flattened_findings_preserve_the_validated_label`: the same content under two reads produces findings with opposite labels that survive flattening through `audit.findings`.
- Ran `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_classification_coherence.py -n0 -q` — 25/25 passed.
- Ran `uv run --no-sync ruff check` on both files — clean.
- Committed with explicit pathspec as `8bec35ac37`.

## Outcome

25 tests passed, 0 failed. Ruff clean. Every `ClassificationCoherenceFinding` and `ModeloClassificationRow` now carries `registry_validated` directly, so a consumer that flattens findings through `RegistryClassificationAudit.findings` or iterates rows without reading the enclosing audit can still distinguish a degraded non-validating read from a validated-authority read. The three new anti-tautology tests prove the label is distinct in both directions and survives flattening.

## Notes

Discovery gate waived by operator — the vaultspec-rag index was broken and the service stopped. Grounded with `rg` plus whole-file reads in lieu of semantic search.

The `_audit()` test helper already passed `registry_validated=False`, so all pre-existing tests that use it required no changes beyond the two sites that directly construct `ClassificationCoherenceFinding`.
