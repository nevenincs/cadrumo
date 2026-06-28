---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-23'
modified: '2026-05-23'
step_id: 'S13'
related:
  - "[[2026-05-22-cli-workflow-redesign-exec]]"
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
---


# `cli-workflow-redesign` `W03.P11.S13` code review

Lead Code Reviewer audit of the W03.S13 commit `d3735bba8` — the IS
LIS Art. 29 rate schedule correction and the entity-type cuota-rate
dispatch.

Status: PASS. No Critical or High findings. Safe to merge.

- Reviewed: `src/aeat/_data/registry/aeat/modelos/200` Modelo 200 records
- Reviewed: `src/aeat/application/overview/_applicability.py`
- Reviewed: `src/aeat/domain/calculations/registry/test_modelo_200_tipo_gravamen_dispatch.py`

## Description

Safety domain. The `lookup_parameter_by_entity_type` dispatch raises a
typed `RegistryValidationError` on an unsupplied or unrecognised
`legal_entity_form` key rather than defaulting a rate — verified by two
dedicated tests. No silent wrong-rate path and no unhandled crash. The
corrected `tipo-gravamen-pyme` `bracket_table` passes the schema's
`_validate_bracket_table_shape` check (non-empty brackets, no
dated-value mixing, declared `bracket_axis`, no overlapping windows);
the 2025 and 2026 `valid_from` windows are disjoint. The change is
declarative registry data plus test code, so there is no resource or
concurrency surface.

Intent domain. The corrected micro-empresa rates (17/20 for 2025,
19/21 for 2026) match the corporate-entity ADR §5 confirmed values
exactly, and the sibling scalar rates (general 25, cooperative 20,
non-profit 10, new-entity 15) match the LIS Art. 29 corpus text. The
dispatch is wired through the `lookup_parameter_by_entity_type` op the
ADR names, keyed on the parent ADR's `legal_entity_form` sub-form. The
micro-empresa bracketed dispatch is deferred with a documented,
technically grounded rationale — the op rejects `bracket_table` and the
flat cuota formula cannot apply a tranche; no design-only shell was
landed. The `_applicability.py` constant rewrite is in-scope hygiene:
the prior comment carried a now-false claim and transient process
labels, a source-hygiene violation.

Quality domain. Every new rate, tranche, formula and binding carries
`legal_refs` to `ley-27-2014:art-29` (and `art-30`), which resolve in
`legal/is.toml`; the construct-closure validator confirms the construct
covers every new member's refs. The cuota oracle in the updated tests
is the AEAT Manual de Sociedades worked example; the rate-schedule
tests assert the registry against the ADR / LIS Art. 29 specification
rather than re-applying a registry formula, and the dispatch tests
assert graph wiring and validation errors. The two updated cuota-chain
tests now exercise the dispatch instead of feeding a hand-typed rate.

## Tests

Registry suite: 1825 passed. The new
`test_modelo_200_tipo_gravamen_dispatch.py` (7 tests) and the updated
`test_modelo_200_registry.py` / `test_cross_dependency_calculations.py`
all green. `ruff` and `ty` clean on every modified Python file.

One Low observation: the shared worktree carries two unrelated
foreign-campaign failures — a `303.toml` oversize gate and an
IVA-wallet binding signature mismatch — both outside W03.S13 scope and
pre-dating this Step. No audit report was opened; they belong to their
originating campaigns.
