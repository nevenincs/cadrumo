---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W01.P01` summary

Implemented the typed calendar evidence model and CLI storage wiring for local filing readiness, AEAT submitted evidence, and justificante verification.

- Modified: `src/aeat/application/overview/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_overview.py`
- Modified: `src/aeat/entrypoints/cli/_overview_payloads.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`

## Description

Wave W01 introduced distinct local and AEAT evidence states, merged local Modelo records, expedientes events, filed-declaration observations, and calculation observations into one calendar evidence model, and wired the CLI to load those stores under the correct profile session.
