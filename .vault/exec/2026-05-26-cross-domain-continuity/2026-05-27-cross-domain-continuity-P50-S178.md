---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S178"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# S178 — Modelo 100 deadline windows exercise 2022 (campaign 2023)

## Outcome

Registered the Modelo 100 deadline window for fiscal year 2022 (campaign filing
in 2023) under `revisions/2022/deadline_windows/0001-modelo-100-2022-0a.toml`.

Dates grounded in corpus `orden-hfp-310-2023.html` (BOE-A-2023-8118) Article 8:
opens 2023-04-11, closes 2023-06-30, payment domiciliation cutoff 2023-06-27.

Added `[legal."orden-hfp-310-2023:art-8"]` to `irpf.toml` with `required_text`
drawn verbatim from corpus Article 8 paragraph 1 and Article 14.3.

Also created `application_links/0011-modelo-100-deadline.toml`.

## Gate

`test_catalogue_verification.py` — 31 passed.
