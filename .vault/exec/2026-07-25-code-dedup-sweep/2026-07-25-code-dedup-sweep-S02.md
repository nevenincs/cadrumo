---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-26'
body_hash: 'sha256:b8f17abb42761e35016f3ac2ee042031b901284d254de548b561bcdb3a7ff8d5'
step_id: 'S02'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---

# Replace the inequality with the predicate at all twenty inner-envelope read paths in one atomic explicit-pathspec commit, each site keeping its exception class and translated message key and per-object context mapping unchanged, and the non-raising contract preserving the usage_ratios except-clause ordering

## Scope

- `10 sites in adapters/persistence/profile/`
- `4 in adapters/outbound/aeat/sede/_observation_store.py`
- `2 in application/workflow/_persistence.py`
- `2 in application/user_profile/_repository.py`
- `application/live/_verify.py`
- `application/live/_snapshot_base.py`

## Description

Replace the ordering comparison with the predicate at all twenty inner-envelope
read paths, each site keeping its exception class, translated message key and
per-object context unchanged.

## Outcome

Delivered by a peer agent. Verified at HEAD rather than assumed.

41 call sites now route through the predicate. The twenty loose comparisons are
gone, and the only four ordering comparisons left in production are exactly the
set the ruling placed out of scope: layer one's ceiling in `_schema_lineage.py`,
a SQL constraint string in `_orm.py`, and the two correctly-paired two-sided
gates on the archive and encrypted-bundle tiers. That the residue matches the
ruling's exclusion list exactly is the check that the sweep was scoped correctly
rather than merely thorough.

**The hardest constraint held.** `usage_ratios` keeps its own raise inside the
`try` whose `except` re-raises `UsageRatioPersistenceError`, so the non-raising
predicate preserved that site's except-clause ordering. A raising helper would
have silently re-routed that path — the specific hazard that defeated the naive
consolidation and the reason the ruling forbade a shared raising helper.
Spot-checked sites also keep their own logging and error identity.

## Notes

Attribution matters here and is stated rather than blurred: this step was
delivered by a peer, and this record exists so a closed checkbox is backed by
verification evidence rather than by an assumption that the plan caused the work.
