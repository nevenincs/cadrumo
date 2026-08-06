---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:15ce503dea719670176a3c5e457f3302a1890f6e1b98121c99c611b39a44bdba'
step_id: 'S04'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M202 04-to-13 advisory on all three loaded revision snapshots

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`

## Description

- Add a parametrized registry-shape test (`2019-2022`, `2023-2024`, `2025-y-siguientes`) to `test_modelo_202_registry.py` that loads the M202 modelo via `_committed_modelo("202")` (the file's existing pattern) and asserts `predicate_id`, `expression == 'implies_nonzero(["04", "13"])'`, `finding_kind == "ADVISORY"`, and both `legal_refs` entries on each loaded revision's `verification_predicates`.

## Outcome

`test_committed_modelo_202_guards_base_imponible_previa_under_declaration[<revision_id>]` ships parametrized across all three revisions, per `no-tautological-calculation-tests` asserting structural shape and legal grounding rather than a hand-computed Decimal. Ran together with S05's gate-behaviour suite: `pytest src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py src/aeat/application/modelo/tests/test_verification_m202_advisory.py -q` -> `20 passed`.

## Notes

No incidents.
