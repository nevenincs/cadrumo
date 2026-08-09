---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6b9c55ff7698a227cd39d1225387454e8ca5a056762fd4239abfb82cb8f109b2'
step_id: 'S20'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name the specific missing taxpayer-model profile facts in the undeclared refusal and raise it through the refusal channel rather than as a parameter error

## Scope

- `src/cadrumo/entrypoints/cli/_overview.py`

## Description

- Added `_undeclared_taxpayer_model_refusal`, which inspects the taxpayer profile and names only the facts genuinely absent: the entity type when unset, or the IRPF income categories when a natural person declared an entity type but no category.
- Routed the calendar, agenda and backlog undeclared-model refusals through it, replacing a Click parameter error carrying a generic sentence.
- Rendered the missing facts through the same shared enrichment helper the completeness refusal uses, so both refusals on the same verb name fields the same way.

## Outcome

An operator blocked by an undeclared taxpayer model is now told which field to fill in, rather than that "the active profile does not declare this taxpayer model".

The conditional branch is the substantive part. The predicate treats the model as undeclared under two different conditions, and a refusal naming both facts unconditionally would send a natural person who HAS declared their entity type back to a field they already answered. Naming only what is absent means the refusal is actionable rather than merely more detailed.

The refusal CONDITION is unchanged. The predicate deciding whether the model is declared lives in the domain layer and was not touched, so exactly the same profiles refuse as before.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py -m integration -n 0 -q
    10 passed in 17.54s

## Notes

**This Step exists because the honesty review found a gap the original inventory missed.** The inventory recorded the completeness-warning refusals on these three verbs and did not record the undeclared-model refusal sitting a few lines above each of them, even though it is the same class of defect on the same verbs. The reference document has been corrected rather than left describing a smaller landscape than the one that was actually there.
