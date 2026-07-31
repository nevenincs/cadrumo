---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:3bf4a8b260594a01f21f12d31c6c8ee5e93c80abfea535d44ca1fbdf867d9444'
step_id: 'S16'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Prove Borrador/Renta Web and portal-open live surfaces are safe read or navigation probes, never submission or form mutation flows

## Scope

- `src/aeat/application/live/_borrador_100.py src/aeat/entrypoints/cli/_app_live_borrador_cli.py src/aeat/entrypoints/cli/_app_live_portals_cli.py src/aeat/adapters/outbound/aeat/sede/tests`

## Description

- Reconciliation closure for the Borrador/Renta Web and portal-open backend
  surfaces. Evidence is the offline real-behavior borrador suites green at HEAD,
  proving the surfaces are read/navigation probes with a roundtrip-stable
  borrador model and no submission or form-mutation path.

## Outcome

The Borrador/Renta Web and portal-open surfaces are proven safe read/navigation
probes by real-behavior tests green at HEAD.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/application/live/tests/test_borrador_100.py src/aeat/application/live/tests/test_borrador_100_roundtrip.py -q`
  passed (batched run: 34 passed with the IVA and CLI-verb suites).
- Portal-open verbs are navigation-only (open an AEAT URL in a browser, no data
  return), covered by `test_live_portals_verbs.py` green at HEAD; no submit or
  form-mutation verb is reachable on either surface.

## Notes

- No live Renta Web borrador positive was captured: the authenticated account
  has no filed declaration and the Cl@ve session could not be driven to a
  post-auth Renta Web landing in this environment. The safe-probe / no-mutation
  contract is proven offline against real behavior; a positive live borrador
  read is carried forward with the operator manual sweep (S26).
