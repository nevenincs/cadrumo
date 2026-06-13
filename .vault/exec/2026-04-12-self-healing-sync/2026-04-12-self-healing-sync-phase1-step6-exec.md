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

# step 6 — settings + env documentation

- `src/aeat/config.py` — added `DivergenceSink` StrEnum and six
  `AEAT_SYNC_*` fields: concurrency, auto-heal allowlist CSV,
  divergence sink, divergence file dir, retry max, retry backoff.
- `env/.env.example` — documented every new var. While there,
  rewrote the mojibake ASCII-art section dividers as clean ASCII
  (the existing file was stored UTF-8 but had undecodable bytes on
  Windows cp1252 that were already breaking
  `tests/test_config.py` before this step; the rewrite restores
  the alignment test on Windows without modifying the test).

All 4 `tests/test_config.py` cases green.
