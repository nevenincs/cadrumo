---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:b8599b599c9bc95b6777692c8b237b57b0d3f8226c9ad19dfa07a534eb995a37'
step_id: 'S03'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Partition the exact-confidence symbol population by owning package and record the dominant kinds per area

## Scope

- `dev/audit`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

The headline 1408 overstates the actionable population by more than half. 602 findings are
`exact`, resolved through the import graph; the other 806 are `name-match` and
`name-match-data`, members reached by attribute access the scan cannot bind to a type. The
exact tier contains only functions, constants and classes -- every enum-member, attribute
and method finding sits in the lower tiers -- so this campaign's symbol work is bounded by
602, not 1408.

The exact population splits by outside use exactly as the modules did: 350 test-only, 198
unreferenced, 54 dev-reached. That split, not the area, is what determines the remedy.

Supersession proved detectable rather than guessed. For a constant, the test is whether its
literal VALUE still appears in production outside its defining module -- the value moved to
a declaration and the name was left behind. Applied to the sixteen unreferenced constants
carrying an inspectable string literal, eleven proved superseded with the live holder named
in each: the error-code registry, the namespace registry, and the CommandSpec declarations.
`_GROUP_HELP_LOCALE_KEY` is the clearest case, its literal now carried by a `TranslationKey`
in the evidence command specs. A name search cannot produce that evidence, which is why the
governing decision requires it for this class.

## Notes on plan revision

The plan's W03 phases were structured by area alone, which the evidence no longer supports:
area determines the size of a diff, but use determines the remedy. Two Steps were added
through the plan verbs rather than worked around -- a supersession sweep that names the live
holder before any removal, and a triage of the test-only population into behaviour that
retires with its test versus seams whose missing production call is itself the defect. The
area Steps stay, because working area by area is still what keeps each diff reviewable.
