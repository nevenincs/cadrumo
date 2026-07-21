---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Extend the ley-37-1992 art-105 required_text with the art-105.Cinco clause, corpus-grounded

## Scope

- `src/aeat/_data/registry/aeat/legal/iva.toml`

## Description

- Extend the `ley-37-1992:art-105` legal entry `required_text` in `iva.toml` with the two art-105.Cinco clauses verbatim from the bundled consolidated LIVA (`ley-37-1992.html#a105`): the interruption-supuesto clause and the "el que globalmente corresponda al conjunto de los tres últimos años naturales en que se hubiesen realizado operaciones" global-percentage rule.
- Extend the entry `notes` to record the art-105.Cinco semantics: a global percentage over the AGGREGATE volumes of the last three ACTIVE años naturales (skipping the interruption gap), not an average of three percentages and not three calendar years.
- Refresh the agent-authored `reviewed_by`/`reviewed_at` provenance for operator re-review.

## Outcome

- Modified files: `src/aeat/_data/registry/aeat/legal/iva.toml`.
- The registry legal-grounding gate `test_registry_legal_grounding.py` cross-checks the two new clauses against the bundled corpus after normalisation and passes (5 passed); the art-105 entry now carries 5 required_text clauses.
- Committed atomically with this exec record and the plan step check.

## Notes

- No new corpus file authored: the art-105.Cinco clause is already present verbatim in the bundled `ley-37-1992.html`, the same file the entry's `corpus_ref` already points at.
- This grounds the art-105.Cinco interrupted-activity seeding rule that Phase P02 (S07-S09) implements: the last-three-active-years global seed walk.
