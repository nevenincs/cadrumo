---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 5 — live sync runner orchestration

- `_runner.py` — `LiveSyncRunner` composes every Protocol stub +
  concrete validator/classifier/dispatcher/repository/strategies.
  Orchestration: cert preload → fetch → validate → classify →
  dispatch → persist → summarise. Exponential backoff retry for
  transient fetch failures bounded by `retry_max` /
  `retry_backoff_s`. `SyncRunResult` is a frozen pydantic v2 model
  that surfaces the full healing plan and per-record outcomes.
- `LivePayloadFetcher` Protocol abstracts the live fetch so the
  runner stays standalone-compilable while #8/#17/#9 are in flight.
- `test_runner.py` — real concrete Protocol doubles (no mocks):
  happy path with additive healing, bounded-policy refusal on
  BREAKING casilla-removal, wire validation failure surface,
  transient-retry success, retry exhaustion raising `SyncError`.

54 unit tests green.
