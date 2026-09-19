---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:ac6409c831d959930ec3f973b9d3542fca0648f934ac7aafe6dde5a31d95c6a7'
step_id: 'S39'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Confine a per-query relevance boost to its own display-class band

## Scope

- `dev/docs/terminology/_unified_record.py`
- `dev/docs/pagefind_inject.py`
- `dev/docs/terminology/tests/test_relevance_boost_band_containment.py`

## Description

- Ground the defect in the code rather than the report: the loader collapses the query-keyed relevance file to one strongest weight per record, and the injector then took the stronger of that and the base weight, capped at 1.
- Author the decision record for the band-with-headroom contract, recording the three rejected alternatives and why the inert clamp is not one of them.
- Derive each display class's band ceiling from the one declared weight table by sorting it, so a reordered or extended table cannot leave a stale hand-listed bound behind.
- Map a boost into its class's band with a reserved margin, so a full boost approaches but never reaches the class above, and a zero boost yields the declared weight exactly.
- Repoint the injector's effective-weight seam at the new containment, keyed on the record's derived display class.
- Gate the invariant over the real committed corpus, preceded by an anchor asserting the corpus actually contains boosts that would escape.

## Outcome

The cross-band promotion is closed. The measured instance was Ley 58/2003 art. 120, boosted to 0.982968 against a legal band floor of 0.75, which placed it above every casilla row at 0.8 and every modelo card at 0.9 that it merely grounds. Of the 90 distinct boosted records in the committed corpus, 55 carried a raw weight at or above their band ceiling, so this was not a single outlier.

Curation keeps its authority and its resolution: within a band, boosts still order records continuously by strength. The declared ladder keeps its authority across bands. Neither now overrides the other.

The top class has no headroom, since its floor is also the ceiling, so a boosted user-documentation record sits at the ceiling and orders by the engine's own lexical score. That is stated in the decision rather than engineered around, because raising the ceiling or lowering that class's floor would reopen the ratified table for a reason the defect does not require.

## Verification

The containment gate passes six tests. The pagefind injection gate, the ladder gate and the display-class gates stay green. Ruff and the formatter pass on the changed files; basedpyright reports 0 errors, 0 warnings and 0 notes.

The gate was proven to bite by restoring the previous behaviour in memory from outside the repository, mutating no tracked file. Under the maximum, band containment fails naming art. 120 at 0.982968 outside `[0.75, 0.8]`, and the higher-class assertion fails reporting that it reaches the casilla class. Under the rejected clamp-to-base alternative, the strict within-band ordering assertion fails reporting that distinct boosts collapsed onto one weight, which is exactly the inertness that rules that option out.

## Notes

The held-out miss rate is deliberately not offered as evidence here. It measures whether a query recalls its target at all and is insensitive to the order the recalled records are presented in, so it cannot detect this defect and does not move when it is fixed. The decision record states that explicitly so a future reader does not read an unchanged miss rate as evidence that this change did nothing.

The relevance file's per-query structure is retained even though the index cannot carry it. It remains the reviewable provenance of why a record is boosted.
