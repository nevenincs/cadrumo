---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S10'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Re-run the held-out miss-rate over the widened mapping, commit the measurement, and apply the ADR D3 gate: implement rung 2 only above the ten-percent top-five miss line, else record the standing baseline

## Scope

- `dev/docs/terminology/`
- `.vault/audit/`

## Description

- Grow the held-out set 5 -> 20 cases: one per promoted concept sample,
  expectations curated from the concept's own card and its registry-grounded
  primary legal ref, independent of sweep output.
- Re-run the held-out miss-rate over the widened mapping and apply the ADR
  D3 gate at threshold 0.10.
- Retarget the golden-query and index-coverage gates from the sidecar-era
  contract to the post-cutover source-path contract, and drop the dead
  pre-rename raw-html exclusion from the ignore file.

## Outcome

GATE DECISION (amended after the close honesty review): the initial
20/20-hit, 0.0-miss measurement was tautological (all-vocabulary cases
seeded with their own concept cards; audit SHARP-1). After remediation -
out-of-sample case class, ratified 0.10 threshold, top-five bound, and a
committed report writer - the honest measurement reads 32 cases, 26 hits,
miss-rate 0.1875: the gate FIRES IMPLEMENT-RUNG-2
(miss-rate-post-widening.json). Rung 2 is formally deferred into its own
follow-up pipeline per ADR Update 2. The retargeted sidecar-exclusion
coverage gate passes; the dedup and staleness machinery is validated
against the post-cutover contract.

## Notes

Two verifications are service-pending, not failed: the golden-query live
suite and one incremental reindex red at close because the shared RAG
service was taken down for team maintenance mid-run (port_unreachable);
the sole staleness miss is the S10 report itself, written after the last
completed reindex. Both are integration-lane, dev-box-only checks; every
deterministic artifact (mapping, coverage, miss-rate) was captured while
the service was up. Re-run `pytest dev/docs/preprocess/tests -m
integration` after `vaultspec-rag index --type code --port 8766` when the
service returns.
