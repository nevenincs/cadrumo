---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:86de6a39638ec8d18459d355393497460aebffd9b678b8b626f089f9273cf55b'
step_id: 'S13'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# BLOCKED on an operator-authorised live specimen capture of Consultar deudas: observe the real situacion label vocabulary and confirm the str Field length bound is adequate, per the Declaracion.estado precedent, with no type change since situacion stays str

## Scope

- `no type change`
- `situacion stays str`
- `src/cadrumo/core`
- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`

## Description

- Reached the consulta under an authenticated session and queried it.
- Established, with a same-session positive control, that the register returns
  no rows for this taxpayer.
- Left `situacion` unchanged: bounded `str`, `max_length=64`.

## Outcome

**DEFERRED CARRY-FORWARD. Not implemented, and nothing in the code changed.**

The row asks for the real `situacion` label vocabulary to be observed and the
string bound confirmed adequate against it. An authenticated session reached the
consulta and queried it successfully; the recaudación register holds no rows for
this taxpayer, so no label exists to observe.

That is established rather than assumed. Within one session the notifications
summary rendered three populated tables while the deudas consulta, queried
immediately after, rendered none — a session returning content elsewhere is
authenticated, un-gated and capable of returning rows.

The field keeps `max_length=64` and stays a bounded `str` per the
`Declaracion.estado` precedent, which is the outcome the row predicted. But the
bound is UNCONFIRMED against real data, not confirmed. Closing this row records
that the observation could not be made; it does not record that the bound was
checked.

## Notes

Unblocks when a listing with rows can be reached. Whoever does that must check
the observed labels against the 64-character bound before trusting it — this row
did not.

Do not close the gap by inventing a vocabulary.
