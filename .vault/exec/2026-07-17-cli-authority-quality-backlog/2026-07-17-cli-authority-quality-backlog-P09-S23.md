---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S23'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---




# Audit the roughly forty select_revision callers and prove every production calculation, verification, filing, export, and projection path resolves through the law-determined canonical resolver and only asserts a stored revision_id equal, never injects it

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_temporal.py`

## Description

- Add `test_every_production_select_revision_call_is_law_determined`: an AST audit over the whole production tree (`src/cadrumo`, tests excluded) that collects every `select_revision(...)` call site with its keyword-name set.
- Assert every call passes the law-determined `filing_year` and `period` axes (both are keyword-only parameters of `select_revision`, so their presence is a faithful proxy for "period-driven selection"), so no call selects by an injected revision id alone.
- Assert any call that also passes `revision_id` (a narrowing assertion, safe under the non-overlap window guarantee) occurs only at the two pinned sanctioned sites — the resolver internal `_snapshot.py` and the creation-time assertion path `_work_addressing.py` — so a new site feeding a stored revision_id into resolution fails review here.
- Add helper `_production_select_revision_calls` and the pinned `_SANCTIONED_REVISION_ID_SITES`.

## Outcome

Audit of the current tree: `select_revision` is the single resolution funnel with exactly 4 production call sites (3 in `_work_addressing.py`, 1 in `_snapshot.py`), all passing `filing_year`+`period`; the only 2 `revision_id`-passing sites are the sanctioned resolver-internal and assertion paths. No production path injects a stored revision_id as the selector. Non-vacuous by construction: the gate asserts call sites were found, and fails on any under-specified call (missing law-determined axes) or any unsanctioned revision_id site. 10 tests pass in the file; ruff clean.

## Notes

No production code changed — coverage-gap gate only. Verified non-vacuity by an independent inline AST probe (4 sites, 0 offenders, revision_id sites == the 2 sanctioned). The `.snapshot(` surface (64 ambiguous sites, most unrelated to registry) was intentionally not enumerated: `select_revision` is the canonical funnel every `authority.snapshot` resolution passes through (`_build_validated_snapshot` calls it with filing_year+period), so gating the funnel is the faithful, robust choke point. git-diff-gated `test_temporal.py` clean at HEAD before editing. Companion to the `revision-resolution-is-law-determined` discipline.
