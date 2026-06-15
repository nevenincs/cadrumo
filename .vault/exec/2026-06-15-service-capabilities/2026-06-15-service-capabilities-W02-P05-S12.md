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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add an Ollama/vision row to ledger providers and a playwright-install remediation hint to BrowserError and ## Scope

- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/adapters/outbound/aeat/browser/session.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
