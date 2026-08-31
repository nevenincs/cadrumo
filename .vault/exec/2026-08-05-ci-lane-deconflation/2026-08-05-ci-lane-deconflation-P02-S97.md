---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7864a7eee7caefa41571c159705a5c0a6c7f7b2cf707a9e3bc1eb3be68055cef'
step_id: 'S97'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Correct a temporal-coverage test that was exercising the WRONG SUBJECT while passing, the first LIVE instance of the positional-selection class rather than a latent one. test_temporal_coverage_expands_open_selectors_through_the_supported_horizon takes modelo 341 and then next(iter(modelo.revisions.values())). Modelo 341 declares two revisions and the iteration order was measured rather than assumed: ['2005-2015', '2016-y-siguientes'], and the selected one is 2005-2015 with year_from 2005. That revision is CLOSED -- its selector carries year_to = 2015 -- while 2016-y-siguientes is the open one, year_to None. So a test whose NAME says it expands OPEN selectors, and whose docstring says a real long-span selector proves later years are not silently skipped, was handed a BOUNDED selector every run. It passed anyway, which is the part worth dwelling on: the assertion compares all report rows against revision_selection_coordinates for the chosen revision, and range(year_from, horizon+1) from 2005 happens to span what the report produces across both revisions. A green test, a truthful-looking name, and the wrong subject -- and nothing in the failure output could ever have revealed it, because there was no failure. THE DISTINCTION FROM THE THREE EARLIER INSTANCES MATTERS. Those broke loudly once a sibling arrived: the route tests tested the wrong row, the M184 gate died on StopIteration, the cross-period fixture would have picked a superseded record. This one does not break at all; it silently under-tests, and would keep doing so indefinitely. That makes positional selection worse than a fragility -- it is a correctness hazard for the SUITE, because a gate exercising a bounded selector cannot catch an open-selector expansion defect no matter how many times it runs green. Fixed by selecting on the defining property, year_to is None, so the subject matches the name. VERIFICATION PENDING AND STATED AS SUCH: ruff is clean, but the test run could not execute -- a peer is mid-relocation in adapters/persistence/storage/custody with untracked new public modules beside the old private ones and the error-code registry half-edited, so AccelerationReceiptRevocationError has no declared entry and the package raises at import. Notably the project's own error text anticipates exactly this, advising the reader to check git status and rerun once the working tree settles. Re-run this module narrowly once it does, and expect a REAL possibility that the corrected test now fails: if open-selector expansion is genuinely broken, this fix is what will finally surface it; `src/cadrumo/application/registry/tests/test_temporal_coverage.py`.
## Scope

- `src/cadrumo/application/registry/tests/test_temporal_coverage.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S97.md`
- `verify:` `pytest -q -n0 src/cadrumo/application/registry/tests/test_temporal_coverage.py::test_temporal_coverage_expands_open_selectors_through_the_supported_horizon` -> `1 passed in 55.58s`

## Notes

Immutable provenance for the original positional open-selector test is `915a66a5bc`; immutable provenance for the subject correction is `be1ad83404`. Neither supplies recoverable historical literal pytest output. S98 is the coupled completion: it corrected the remaining multi-revision composition assumption exposed after S97 selected the right open revision. This record attests only the fresh focused receipt above.
