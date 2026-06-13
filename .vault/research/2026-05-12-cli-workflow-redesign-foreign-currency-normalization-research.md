---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `foreign-currency-normalization`

## Findings

Financial providers carry currency codes, but the application has no FX
normalization layer. Existing default-currency settings are not enough because
non-EUR source values must retain source currency, rate provenance, and
normalized EUR amount.

Banco de España publishes currency conversion resources and historic exchange
rate data. Source:
`https://www.bde.es/webbe/es/estadisticas/recursos/conversor-divisas.html`.

Target placement is `application/aggregation`, before modelo bindings consume
monetary values. Evidence records keep original amount, original currency,
rate source, rate date, normalized EUR amount, and normalization status.

Reject normalizing inside BOE exporters, silently assuming EUR via
`default_currency`, per-provider conversion logic, and binding-time shims.
