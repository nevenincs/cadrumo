---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `calendar-live-operational-hardening` `W01.P01` summary

Registry live-read boundaries were hardened after authenticated AEAT verification.

- Modified: `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes/live_cross_references/0001-live_cross_references.toml`
- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/test_filed_bulk_capture.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_190_registry.py`

## Description

Modelo 190 now declares the real AEAT declarations-register host. Bulk filed capture derives unsupported local boundary rows from registry revision metadata, proven with Modelos 151 and 721.
