---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0c07df804ffa360677e7a1770939e2d10df130347bbcb8b774de79b08321e106'
step_id: 'S98'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Finish the temporal-coverage correction and VERIFY it: 39 passed sequentially. The prediction in the sibling Step held exactly -- pointing the test at its stated subject made it FAIL, and the failure was informative rather than a regression. With the open revision selected, report rows carried coordinates such as (2014, '2T') that no open-selector expectation could account for, because _authority_with_single_model composes a single MODELO and modelo 341's closed 2005-2015 sibling contributes its own rows. The assertions compare every report row against ONE revision's coordinates, which is only meaningful when that revision is the only one composed. So the test carried TWO coupled defects, and fixing only the first would have left it red: it selected its subject positionally, AND its assertion silently assumed a single-revision modelo. The original green run was the product of those two errors cancelling -- the closed revision's year_from of 2005 made range(2005, horizon+1) span everything the report produced across both revisions, so a bounded selector satisfied an assertion written for an unbounded one. Fixed by composing the authority from the open revision alone, which makes both assertions exactly about open-selector expansion, and the module is green. WHY THIS IS THE MOST INSTRUCTIVE INSTANCE OF THE CLASS SO FAR: the three earlier ones broke loudly the moment a sibling arrived. This one never breaks. It under-tests silently and permanently, and no amount of running it green could reveal that, because there is no failure to inspect -- the only way to find it was to ask what subject the selection actually returns and measure the iteration order rather than assume it. A gate exercising a bounded selector cannot catch an open-selector expansion defect however often it passes, so positional selection is not merely fragile here; it quietly removes coverage the suite believes it has. That is the argument for treating the remaining S96 sites as worth auditing rather than leaving until something goes red, since by construction these will not; `src/cadrumo/application/registry/tests/test_temporal_coverage.py`.
## Scope

- `src/cadrumo/application/registry/tests/test_temporal_coverage.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S98.md`
- `verify:` `pytest -q -n0 src/cadrumo/application/registry/tests/test_temporal_coverage.py::test_temporal_coverage_expands_open_selectors_through_the_supported_horizon` -> `1 passed in 56.79s`

## Notes

Immutable implementation provenance is `be1ad83404`. No historical literal receipt exists for the plan row's 39-pass claim; this record attests only the fresh receipt above. S97 corrected the selected open-revision subject; S98 completes that correction by composing the authority from that revision alone; S99 confirms M341 is a real confirmed positional-selection finding.
