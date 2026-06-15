---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S12'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Add an Ollama/vision row to ledger providers and a playwright-install remediation hint to BrowserError

## Scope

- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/adapters/outbound/aeat/browser/session.py`

## Description

- Add `VisionProviderPayload` and a `vision: VisionProviderPayload | None` field to `LedgerProvidersResult` so the providers envelope reports the on-host Ollama vision backend alongside the subprocess cloud CLIs.
- Populate the vision row in the `ledger providers` command by calling `probe_ollama_vision`, fixing an over-deep relative import (`....application` → `...application`).
- Add a `playwright install chromium` remediation hint to the `BrowserError` raised on Chromium-launch failure when the driver message indicates a missing executable.

## Outcome

`aeat app ledger providers` now surfaces every classification backend — cloud and local — in one place, and a missing Playwright browser yields an instructive install hint instead of a raw stack trace. 15 provider/payload tests and JSON-schema conformance (94 schemas) pass. Committed as `b74bd205e`.

## Notes

None.
