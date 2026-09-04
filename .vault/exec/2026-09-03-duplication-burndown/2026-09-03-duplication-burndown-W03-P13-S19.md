---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8ec2e3c7e63d6041dd565d6ed1dbcdfda2451bbfea45652433e219e319a2bd12'
step_id: 'S19'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Consolidate the duplicated Ledger injected-action validation into one guard, closing the review-action check the direct construction path omitted

## Scope

- `src/cadrumo/entrypoints/tui/ledger`

## Changes

- `A` `src/cadrumo/entrypoints/tui/ledger/action_guards.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" src/cadrumo/entrypoints/tui/ledger` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/ledger/` -> `pass`

## Notes

The duplication hid a missing guard, which is the finding.

The route factory and the workspace controller each validated the injected Ledger actions
against the same canonical command keys. The factory checked four -- review, classify,
evidence, link. The controller checked three: it never verified that `review_action`
resolves to `ledger.review`, and its only reference to that key is a routing-table entry.
So every caller constructing the controller directly, which is the devtools workbench
fixture and ten flow tests, skipped that refusal entirely while the factory path enforced
it.

That is what writing a guard twice produces: not two copies of one rule, but two rules that
drifted. The check now lives in one module both paths call, so a future check cannot land
on a single path. The controller gained the review-action refusal it was missing, and 75
TUI ledger tests pass with it.

Teeth proven directly against the guard: a review action that resolves to classify, a
classify action that resolves to review, and a link action that resolves to review are each
refused with their own message.

## Notes on the clone this Step's sibling targets

The clone count is unchanged at 11, and that is expected rather than a shortfall. What
jscpd matches between these two modules is the eleven-parameter SIGNATURE, not the
validation, so consolidating the validation cannot move it.

Removing the signature clone needs the dependency-bundle refactor, and its blast radius is
larger than the estimate given when it was authorised. The controller is constructed at
twelve sites, not two: the route factory, the devtools workbench fixture, and ten call
sites across the flow tests, each passing a different partial keyword set and several
carrying explanatory comments about why a particular argument is present. Every one would
have to be rewritten, inside a TUI surface another campaign is actively developing.

That correction is recorded here rather than acted on, because the authorisation rested on
the smaller estimate.
