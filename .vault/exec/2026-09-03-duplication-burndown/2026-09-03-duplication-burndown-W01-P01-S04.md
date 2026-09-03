---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:19ccec259742d61145a3b61fcf6490bf53f1045bb232d59239d4b467a01c7ddd'
step_id: 'S04'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Recover and reconcile one disposition for every currently observed clone group without carrying stale groups or muting findings

## Scope

- `dev/audit/duplication_dispositions.toml`

## Changes

- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync python -m dev.audit.duplication` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`

## Notes

Every one of the 52 observed groups is classified `cluster-owned`; none is `intentional`.
The governing decision requires a literal observed-zero close and states that a
disposition never excuses a positive detector result, so an `intentional` entry could not
close a group here -- it would leave the detector positive. The classification stays
defined in the header for the post-campaign rolling ratchet.

`reconciled_groups` now equals `observed_groups` (52). That is a statement about coverage
of this ledger, not about the tree: the tree still carries all 52 clones and the runner
still reports them. Verified non-suppressive -- the scan reports 52 clones and 0.21%
before and after this change.

The seven clusters were derived from the live file-sets, not assumed: 43
ledger-command-declarations, 3 application-local-authorities, 2
modelo-nonwork-command-declarations, and one each of ledger-renta-gastos-bindings,
modelo-export-review-package, sede-check-mechanics, tui-ledger-controller-routes.

Coverage proven by the restored multiset read: 27 distinct file-sets, 52 recorded, 0
uncovered. Teeth proven both ways against the live set -- injecting a surplus clone into
an already-recorded file-set is detected, and so is a brand-new file-set.

The previous revision of this file cited a plan Step identifier in its header. That
citation was removed rather than carried forward: the Code Stands Alone mandate forbids
configuration from referencing vault documents or Step ids, so clusters are named
descriptively instead.
