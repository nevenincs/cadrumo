---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:0c242306bfbc41377958e5926b6e73e7e080afa16fb5fa4b95d1b5395c4fb1a4'
step_id: 'S02'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Run the held-out golden queries through the shipped relevance mapping with the miss-rate machinery and commit the baseline miss-rate report

## Scope

- `dev/docs/terminology/_miss_rate.py`
- `.vault/audit/`

## Description

- Run `evaluate_held_out_miss_rate()` over the shipped relevance mapping
  with an isolated storage root.
- Adjudicate rung 2 at the ADR D3 threshold 0.10.
- Commit the baseline artifact
  `src/cadrumo/_data/terminology/evaluation/miss-rate-baseline.json`.

## Outcome

5 of 5 held-out cases hit; miss-rate 0.0 over the 72-query / 29-concept
compiled mapping; rung-2 decision keep-deferred. Committed in `485ac85614`.

## Notes

Five cases is too thin a denominator for a ten-percent gate; the held-out
set must grow alongside the W03 vocabulary widening.
