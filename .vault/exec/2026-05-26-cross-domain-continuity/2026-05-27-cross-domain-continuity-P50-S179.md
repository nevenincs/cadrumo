---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S179"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# S179 — Modelo 100 deadline windows exercise 2024 (campaign 2025)

## Outcome

Registered the Modelo 100 deadline window for fiscal year 2024 (campaign filing
in 2025) under `revisions/2024/deadline_windows/0001-modelo-100-2024-0a.toml`.

Dates from the AEAT-published 2024 campaign: opens 2025-04-02, closes 2025-06-30,
payment domiciliation cutoff 2025-06-25. Authority: `orden-hac-242-2025` (BOE-A-2025-5049).

Added `[legal."orden-hac-242-2025:art-8"]` to `irpf.toml`. The corpus only contains
artículo primero (form approval); Article 8 text has not yet been extracted to the JSON
corpus, so `required_text` is omitted to avoid a false corpus-verification failure.
The `corpus_ref` points to `orden-hac-242-2025.json#articulo-8` as the intended
anchor for future corpus completion.

Also created `application_links/0010-modelo-100-deadline.toml`.

## Gate

`test_catalogue_verification.py` — 31 passed.
