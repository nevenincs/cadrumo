---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f970be3d957d32349b0d08358c8d8e7a4beed463e1788710bf37f9483958941b'
step_id: 'S80'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Test the previous step's lesson across every gate rather than only the one that bit, and adjudicate the period vocabulary: thirty-nine tree-scanning gates assert emptiness with no population floor, but none scans a path that no longer exists, so the false-green shape found in the lazy-facade gate did not repeat; the twelve missing literals are all synthetic fixture paths inside detector-teeth cases. Classify the scenario validator body as reached by the two harnesses its docstring names, and keep the period enumerator family whole on the symmetry argument.

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1040, exact 411,
  unadjudicated 218 -> 215; no symbol moved, this step adjudicates
- `verify:` `python -m dev.quality.unreachable_module_ratchet`,
  `... secure_store_write_path` exit 0; duplication 10 / 0.05%; dead code 0
- `verify:` ledger validated -- 121 clusters, 280 symbols, no double classification

## Notes

The previous step found a gate that had lost its subject without failing, so
this one asked whether the shape repeats. Two probes, both negative. Thirty-nine
tree-scanning gates assert emptiness with no population floor, which is the
vulnerable shape; none of them names a directory that no longer exists. The
twelve literal paths that do not resolve are all synthetic fixtures inside
detector-teeth cases -- `_impostor.py`, `test_leftover.py`, `a.py` -- which is
the opposite of the defect: those gates plant a file that must not exist in
order to prove they can see one.

A negative result is the outcome, not a failure to find work. The lazy-facade
gate lost its subject because a RETIREMENT completed under it; a gate whose
population is a standing corpus cannot go vacuous the same way, and thirty-nine
missing floors are a shape rather than thirty-nine defects.

`hydrate_scenario_filing_period` is reached by both consumers its docstring
names, and a first pass concluded the opposite. The grep was truncated by
`head -4` and the four lines it printed were all from one test module. This is
the third time in this campaign that a truncated command has manufactured a
finding.

The period enumerators are kept whole. They form a two-by-two family of
{registry, filing} x {codes, patterns}, and the registry selector token-parity
test enumerates THROUGH `accepted_period_codes` so its coverage cannot drift
from the accepted set. Deleting the members with fewest callers would leave a
vocabulary that can enumerate its registry codes but not its filing patterns.
