---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S176"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# S176 — Modelo 100 deadline windows exercise 2020 (campaign 2021)

## Outcome

Registered the Modelo 100 deadline window for fiscal year 2020 (IRPF campaign filing
in 2021) under `revisions/2020/deadline_windows/0001-modelo-100-2020-0a.toml`.

Dates grounded in corpus `orden-hac-248-2021.html` (BOE-A-2021-4238) Article 8:
opens 2021-04-07, closes 2021-06-30, payment domiciliation cutoff 2021-06-25.

Added `[legal."orden-hac-248-2021:art-8"]` to `irpf.toml` with `required_text`
drawn verbatim from corpus Article 8 paragraph 1 and Article 14.3.

Also created `application_links/0010-modelo-100-deadline.toml` to satisfy
the catalogue constraint that deadline_windows require a deadline application link.

## Gate

`test_catalogue_verification.py` — 31 passed.
