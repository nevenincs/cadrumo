---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S34'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Define the structured applies_when frontmatter schema and its parser over TaxpayerProfile facts and lifecycle state

## Scope

- `src/aeat/agent/_skill_metadata.py`

## Description

- Author the `SkillAppliesWhen` pydantic v2 model with three orthogonal axes: `profile_facts` (a tuple of conjunctive predicates), `workflow_phase`, `temporal_trigger`, and an exclusive `always` flag for cross-cutting helpers.
- Author the `ProfileFactPredicate` model carrying a `fact` name, a closed `ProfileFactMatch` enum (`present`, `absent`, `equals`, `contains`, `is_true`, `is_false`), and a `values` tuple.
- Derive the valid fact-name set and the per-fact enum-value sets from the live `TaxpayerProfile` model at import through annotation introspection, never a hand-maintained list, so a typo'd fact name or an invalid enum member fails load.
- Enforce match/kind coherence: `contains` only on collection facts, `is_true`/`is_false` only on boolean facts, `equals` only on scalar facts, and `present`/`absent` take no values.
- Add the `WorkflowPhase` and `TemporalTrigger` closed enums covering the helper lifecycle points and the six life-situation triggers the WHEN layer consumes.
- Add `parse_skill_frontmatter` and `parse_skill_metadata` to extract and validate a `SKILL.md` YAML frontmatter block, raising the typed `SkillMetadataError` on any invalid predicate.
- All models use `extra="forbid"` and are frozen.

## Outcome

New module `src/aeat/agent/_skill_metadata.py` provides the machine-queryable selection-predicate schema and its frontmatter parser. A standalone probe confirmed every acceptance path (contains-on-frozenset, equals-in-set, workflow_phase, always) and every rejection path (typo fact name, invalid enum value, contains-on-scalar, is_true-on-non-bool, no-axis, always-exclusive, extra key, values-on-valueless-match, bad enum member, missing frontmatter). Ruff check/format clean; pyright reports 0 errors on the module.

## Notes

Dropped `strict=True` from the model configs: pydantic v2 strict mode refuses to coerce a YAML list into the `tuple` fields, and YAML frontmatter always yields lists. Lax mode still rejects int/bool-to-str coercion, so scalar-type safety is preserved, and the fact-name and enum-value validators (the load-bearing typo guards) run irrespective of strict mode.
