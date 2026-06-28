---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `festivos-deadline-shift`

## Findings

`DeadlineEngine.compute` currently uses `window.closes_on` directly and has no
holiday/calendar dependency. This means app overview calendar/today cannot
reliably explain adjusted due dates.

AEAT calendar guidance says that when a presentation deadline falls on a
non-business day, the deadline generally moves to the next business day, with
noted exceptions such as Modelo 369. Source:
`https://sede.agenciatributaria.gob.es/Sede/gl_es/ayuda/calendario-contribuyente/calendario-contribuyente-2025/recuerde/vencimientos-dias-inhabiles-sabados-festivos.html`.

Target implementation is a pure holiday-adjustment service under
`domain/deadlines`, consumed by `app overview calendar` and
`app overview today`. The service must preserve original close date, adjusted
close date, calendar source, jurisdiction layer, and modelo-specific exception
reason.

Reject Rich-only CLI fixes, hardcoded 2026 tables in CLI code, legacy
profile-path reads, silent date shifting without explanation, and CLI shims
that bypass the domain engine.
