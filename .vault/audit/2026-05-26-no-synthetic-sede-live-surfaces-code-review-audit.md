---
tags:
  - '#audit'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
---

# `no-synthetic-sede-live-surfaces` Code Review

No CRITICAL, HIGH, MEDIUM, or LOW implementation defects found in the
no-synthetic-Sede changes.

Reviewed surfaces:

- `LiveCrossReferenceDecision` rejects AEAT-hosted `synthetic_data_allowed = true`
  declarations at schema validation time.
- `RemoteStateGuardPolicy` rejects AEAT-hosted `synthetic_data_allowed = true`
  runtime policies before remote preflight.
- AEAT host matching is centralized in `_aeat_hosts` and uses the configured
  `agenciatributaria.gob.es` suffix plus the ADR-required legacy `aeat.es`
  suffix.
- Modelo 100 Renta WEB Open and Modelo 349 GROI/IXVI committed
  cross-references advertise `synthetic_data_allowed = false`.
- Direct outbound GROI and NIF-IVA Sede guard policies advertise
  `synthetic_data_allowed = false`.
- Remaining `synthetic_data_allowed=True` hits are negative tests or
  non-AEAT-host examples, not AEAT-hosted live-surface policy.

Residual validation note:

- A broader Sede declarations batch still fails three unrelated Modelo 303
  export-layout tests on `modelo-303-envelope-marker`. This is not caused by
  the no-synthetic-Sede policy slice and remains concurrent Modelo 303 WIP.
