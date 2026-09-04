---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e589e73c8a46c38d6dce4560312687da2f1d39447248e067a5ab1a91fe50ff02'
step_id: 'S17'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Reconcile final dispositions to the live clone set and remove entries for resolved groups

## Scope

- `dev/audit/duplication_dispositions.toml`

## Changes

- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`

## Notes

Reconciled: the live scan reports 10 clone groups, the record carries 10 dispositions across
9 distinct file-sets, and the multiset coverage read reports 0 uncovered. Entries for the 42
groups resolved during the campaign were removed as their clones disappeared, which is what
this record's contract requires -- a disposition describes a group observed NOW, so a
resolved entry loses no reasoning.

Nine groups are `cluster-owned` and one is `intentional`: the Modelo export and
review-package handler signatures, which the dispatch contract forces to be spelled twice.

## Notes on tooling that failed here

Reconciliation is regenerate-then-reapply, and the regeneration DROPPED the adjudicated
group: it emitted 9 groups while the summary still claimed 10, because the generator's emit
loop only writes groups whose cluster name it recognises and `intentional` is not one.

Both arithmetic gates caught it -- the original totals check reported "summary sums to 10 but
there are 9 recorded groups", and the per-class check added in the previous Step reported
the `cluster-owned` count as recorded 10 against actual 9. The ledger was restored from the
copy taken before regenerating.

That is the second time this campaign's own tooling tried to discard an adjudication, and
the reason the gates matter more than the generator: a script that silently drops the one
group carrying a reasoned decision is exactly the failure a coverage-only check would pass.
The re-application step now lives in its own small script rather than inside the generator,
after two attempts to add it there left syntax errors.
