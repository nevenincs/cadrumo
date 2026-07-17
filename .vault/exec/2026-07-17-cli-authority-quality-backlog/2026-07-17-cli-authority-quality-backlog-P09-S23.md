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
- Factor the extraction (`_select_revision_calls_in_tree`) and classification (`_law_determined_violations`) into shared helpers, and pin `_SANCTIONED_REVISION_ID_SITES`.
- Add `test_law_determined_gate_catches_injected_revision_id_selection`: a discrimination (anti-tautology) proof that feeds synthetic module sources through the SAME extraction + classification the production gate runs, asserting the gate flags (a) a revision_id-only selection missing the law-determined axes, and (b) a revision_id injected from an unsanctioned module, while (c) passing the correct law-determined shape clean.

## Outcome

Audit of the current tree: `select_revision` is the single resolution funnel with exactly 4 production call sites (3 in `_work_addressing.py`, 1 in `_snapshot.py`), all passing `filing_year`+`period`; the only 2 `revision_id`-passing sites are the sanctioned resolver-internal and assertion paths. No production path injects a stored revision_id as the selector. The gate is proven non-vacuous by an in-test discrimination proof (not just by construction): it demonstrably fails on a deliberately-wrong injection and accepts the correct shape, so it cannot silently pass green while the invariant is broken. 11 tests pass in the file; ruff clean.

## Notes

No production code changed — coverage-gap gate only. The `.snapshot(` surface (64 ambiguous sites, most unrelated to registry) was intentionally not enumerated: `select_revision` is the canonical funnel every `authority.snapshot` resolution passes through (`_build_validated_snapshot` calls it with filing_year+period), so gating the funnel is the faithful, robust choke point. The discrimination proof shares the production gate's exact extraction/classification helpers, so a green proof is evidence the real gate discriminates. git-diff-gated `test_temporal.py` clean at HEAD before both edits. Companion to the `revision-resolution-is-law-determined` discipline.
