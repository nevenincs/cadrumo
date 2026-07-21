---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S15'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Amend the latency ADR to authorize count and date-span OUTSIDE_PERIOD summaries

## Scope

- `.vault/adr/2026-07-05-ledger-latency-budget-adr.md`

## Description

- Load the ADR workflow guidance before editing the accepted decision.
- Attempt ADR-filtered semantic search for the out-of-window diagnostic summary decision.
- Read the accepted latency ADR, the performance research artifact, the ADR template, and current out-of-window diagnostic code anchors.
- Amend the accepted ADR to authorize one count/date-span `OUTSIDE_PERIOD` summary diagnostic per resolver/window.
- Preserve the O2 constraints: no declared-value changes, no regulated gate reordering, no plaintext index widening, and full-scan fallback on stale indexes.

## Outcome

The latency ADR now carries a 2026-07-06 diagnostic-summary amendment. It permits repository-backed resolvers to collapse uniform out-of-window `OUTSIDE_PERIOD` rows into one diagnostics-channel summary carrying only excluded count and filing-date span. The amendment explicitly forbids decrypted financial fields and leaves in-window observations, casilla values, provenance, gate order, index schema, and stale-index fallback unchanged.

## Notes

The ADR-filtered `vaultspec-rag` search returned no results because the local vault index is incomplete after the service disk-space failure. Direct reads of the accepted ADR, research artifact, ADR template, and current code anchors supplied the grounding for the amendment.
