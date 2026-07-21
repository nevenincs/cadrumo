---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S369'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# MEDIUM clarify applicability_conditions Python-vs-TOML split per discovery1 #149

## Scope

- `closed as no-code verification: RAG and source inspection confirm modelo-level applicability is canonical in src/aeat/domain/calculations/registry/_applicability.py`
- `the stale application overview copy is absent`
- `and no non-test duplicate _MODELO_APPLICABILITY_RULES assignment remains`
- `src/aeat/domain/calculations/registry/tests/test_applicability_canonical.py passes 4/4`
- `src/aeat/domain/calculations/registry/`

## Description

- Ground the authority boundary through the RAG index and inspect the registry applicability module and the deadline-window contract.
- Search the production tree for duplicate applicability-rule-table assignments.
- Run the direct canonical-applicability regression suite and Ruff.
- Obtain an independent review of the code-versus-TOML boundary and correct the stale test-count wording through the plan CLI.

## Outcome

Modelo-level applicability has one canonical Python authority. TOML applicability conditions operate only after that gate, selecting among otherwise applicable deadline windows. The retired application shim is absent, the public facade retains object identity with the canonical function, and the current three-test suite passed with Ruff. Independent review found no split-authority regression.

## Notes

The prior step text stated that the focused test passed four cases. The current direct suite contains three tests; the plan action was corrected through the plan CLI before closure. This is evidence wording drift only.
