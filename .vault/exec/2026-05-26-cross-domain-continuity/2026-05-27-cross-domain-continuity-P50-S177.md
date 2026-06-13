---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S177"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# S177 — Modelo 100 deadline windows exercise 2021 (campaign 2022)

## Outcome

Registered the Modelo 100 deadline window for fiscal year 2021 (campaign filing
in 2022) under `revisions/2021/deadline_windows/0001-modelo-100-2021-0a.toml`.

Dates grounded in corpus `orden-hfp-207-2022.html` (BOE-A-2022-4296) Article 8:
opens 2022-04-06, closes 2022-06-30, payment domiciliation cutoff 2022-06-27.

Added `[legal."orden-hfp-207-2022:art-8"]` to `irpf.toml` with `required_text`
drawn verbatim from corpus Article 8 paragraph 1 and Article 14.3.

Also created `application_links/0011-modelo-100-deadline.toml`.

## Gate

`test_catalogue_verification.py` — 31 passed.
