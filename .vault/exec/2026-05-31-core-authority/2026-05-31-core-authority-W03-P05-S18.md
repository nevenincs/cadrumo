---
tags:
  - '#exec'
  - '#core-authority'
step_id: S18
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P05.S18 — Replace RENTA_WEB_OPEN_APP_URL with lazy Settings read (RELOC-008)

## Change

Removed module-scope `RENTA_WEB_OPEN_APP_URL` constant from
`domain/calculations/registry/_renta_web_open_oracle.py` and its re-export from
`domain/calculations/registry/__init__.py` and
`adapters/outbound/aeat/sede/_renta_web_open.py`.

Changed `RentaWebOpenLivePayload.app_url` field from bare constant default to
`Field(default_factory=lambda: AnyUrl(Settings.external_constants().aeat.oracles.renta_web_open_app_template.format(year=2025)))`,
deferring the Settings call to construction time (Rule 6 compliant).

Updated test files (`test_renta_web_open.py`, `test_renta_web_open_oracle.py`)
to remove the constant import and compute URLs via `Settings.external_constants()`.

## Verification gate

Renta WEB Open oracle and sede driver test suites — passed sequentially.

## Commit

Committed as part of W03.P05 URL constant lazy-reads block (combined with S17).
