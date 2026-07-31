---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:4984d5133c9d574b350f87e0eea14cca2ae5e1b35ba592aec5215ec24256dfde'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `modelo-036-037-foundation`

## Findings

`registry/aeat/modelos/036.toml` and `037.toml` are absent, though portal
entries exist. AEAT says Modelo 037 was suppressed from 2025-02-03 and that the
simplification represented by Modelo 037 moved into Modelo 036. Source:
`https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/calendario-contribuyente/calendario-contribuyente-2026/informacion-sobre-presentacion-modelos-no-periodicos/modelo-036.html`.

Target implementation is a Modelo 036 registry foundation and app modelo
lifecycle support for event-triggered `alta`, `modificacion`, and `baja`.
Modelo 037 remains historical metadata only, inactive and superseded.

Reject portal-only support, setup wizard substitute, integer modelo codes,
live submission, and shims that keep Modelo 037 active after suppression.
