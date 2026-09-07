---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:ac726140ebf168baa1676bc4eb435e072a1a3495cfa4a4137b78814d11aef254'
step_id: 'S88'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Close the orphaned-test coverage gap the owning gate reported once the schema repair let it run: fourteen test modules were neither entered nor under a classified module, so nobody had decided their fate, and each names in the audit output the module or symbol finding it exercises. Enter all fourteen as derivative entries anchored to what they follow, four of them under the compatibility-lifecycle module and two under the CRUD contract, the rest following an unused symbol.

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest dev/audit/tests/test_reachability_classification.py` 9 passed
  -- the owning ledger gate is fully green for the first time this campaign
- `verify:` `... test_ledger_citations_resolve.py
  ... test_ledger_measurements_are_dated.py
  ... test_classification_taxonomy_invariants.py` 19 passed
- `verify:` module ratchet, secure-store gate and docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0; unused 1038, exact 409
- `verify:` symbol ratchet exits 1 on the same two peer lines
- `verify:` `test_module` entries 2 -> 16; twenty-four orphaned tests reported,
  all now covered

## Notes

The previous step repaired the ledger's schema, which let the owning gate run
for the first time; this step pays what it then reported. Fourteen orphaned test
modules were neither entered nor under a classified module, which means nobody
had decided their fate -- the exact condition the gate exists to refuse.

None needed judgement invented for it. The audit already records, per orphaned
test, the module or symbol subjects it exercises, so the anchor is derivable
rather than assigned: four follow `core.compatibility_lifecycle`, two follow the
operator-surface CRUD contract, and the remaining eight follow an unused symbol
in a named module. Entered as derivative, which is what the whole non-TUI
orphaned-test population is -- each retires with its subject and carries no
independent remedy.

Two steps in a row have found debt that existed only because the owning gate was
not being run. The schema errors hid the coverage gap, and the coverage gap
would have hidden the next thing. Running the gate is the check; a script that
validates what its author remembered to check is not.
