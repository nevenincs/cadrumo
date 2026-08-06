---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:356ae00817081282eeec5599cf63aa4654749929f8ea081dcc2696fc74d157b8'
step_id: 'S15'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Build the full-screen application shell and the question-page screen with the fixed zones (header progress, prompt, help, badge, format hint, widget, live validation line, answer echo, keybinding footer)

## Scope

- `src/cadrumo/adapters/inbound/tui/`

## Description

- Build the Textual full-screen application shell over the engine and the question-page screen with the fixed zones (header progress, prompt, help, badge, format hint, widget, live validation line, answer echo, keybinding footer).
- Land the page design pass and render choice pages as a numbered-list widget family.
- Landed in `b38a036bae`, refined by the design pass `9803d782ec` and the numbered-list family `4d4be90578`.

## Outcome

The full-screen frontend presents each question with all fixed zones and live validation, driving the same engine the line and scripted frontends use. The migrated wizard defaults to this frontend (`9803d782ec`).

## Notes

None.
