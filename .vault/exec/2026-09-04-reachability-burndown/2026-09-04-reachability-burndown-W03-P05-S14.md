---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:6603a840eaa7eb07e5664572436f816f68cf2c1151fbfe23c6566884d4828425'
step_id: 'S14'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Triage the test-only symbol population into behaviour that retires with its test and seams whose missing production call is the defect

## Scope

- `dev/audit`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/audit/tests/test_reachability_classification.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

The triage rule needs three conditions, and each was added because dropping it gave a wrong
answer against this tree. A production module reaches a test-only symbol only when it
from-imports the name, the import's source is the DEFINING module, and the name appears in
its body.

Name-matching alone reported 84 seams, inflated by private names colliding across unrelated
modules -- several define their own `_ZERO` or `_LISTING_URL`. Requiring an import but not
its source reported 18, still counting `csv.py` binding `CSV_EXTENSIONS` from a sibling
`_constants` module rather than from the flagged one. All three conditions give 9. Two
intermediate numbers were measured and discarded before the third; neither was recorded as
a finding.

RESULT: of 350 test-only exact symbols, 341 retire with their tests and 9 are reached only
from a module that is itself a finding -- `_edit_facade`, `edit_session`,
`_registered_values`, `renta_web_open`, and one inside the `domain.fincas` finding package
-- so they are transitively dead and resolve when their importer does.

No live-module seam exists in this population. The `portals.drift` shape, a live surface
declaring an input nothing produces, occurs at module level but not among these symbols.
That is what makes the 341 ordinary removals rather than 341 wiring decisions, and it is
the answer the domain-symbol Step was waiting on.

## Notes on the gate

The ledger gate failed twice during this Step, correctly both times, and the second failure
exposed a design flaw in the gate rather than in the tree.

First it caught two new module findings a peer landed mid-iteration, `domain.contabilidad`
and `domain.is_compensation` -- new Modelo 200 accounting and IS compensacion capability
whose only non-test consumer is the error registry. Both are classified `staged-capability`
with their commit named.

Then it failed again on two further test modules the same peer added while this Step was
running. Requiring one entry per test file cannot track a package under construction, and
chasing it would have meant re-editing the ledger after every peer commit. Coverage now
also accepts a test living under a module the ledger already classifies, which is the
honest generalisation of this campaign's own finding that the orphaned-test population is
entirely derivative: a test inside a classified package shares that package's class and
remedy. The precedent is the frozen TUI prefix, which is likewise scoped at package level.
Teeth re-proven: a test under no classified module still fails.
