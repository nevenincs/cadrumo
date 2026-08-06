---
tags:
  - '#exec'
  - '#core-authority'
step_id: S17
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:59711ca79321c27ba14e95da79b4b125c8dc4d6601f374d6ca1d7c28406f8eb8'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P05.S17 — Replace RENTA_WEB_OPEN_LANDING_URL with lazy Settings read (RELOC-007)

## Change

Removed module-scope `RENTA_WEB_OPEN_LANDING_URL` constant from
`domain/calculations/registry/_renta_web_open_oracle.py` and its re-export from
`domain/calculations/registry/__init__.py`.

Updated the landing URL test to compute the URL directly from
`Settings.external_constants().aeat.domains.sede + .aeat.help_pages.renta_web_open_landing`.

## Verification gate

Renta WEB Open oracle test suite — passed sequentially.

## Commit

Committed as part of W03.P05 URL constant lazy-reads block (combined with S18).
