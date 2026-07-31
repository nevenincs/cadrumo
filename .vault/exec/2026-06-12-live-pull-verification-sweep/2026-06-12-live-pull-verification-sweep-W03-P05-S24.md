---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:8b657e85cfddb1f53bd7040ae26feebabf5ef4ac8b87d783611e867eafb58d26'
step_id: 'S24'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Exercise verify and portal CLI commands as safe read/navigation probes with explicit refusal for anything write-shaped

## Scope

- `src/aeat/entrypoints/cli/_app_live_verify_cli.py src/aeat/entrypoints/cli/_app_live_portals_cli.py src/aeat/entrypoints/cli/tests/test_live_portals_verbs.py`

## Description

- Reconciliation closure for the verify and portal CLI command surfaces.
  Evidence is the offline portals-verb suite and the live verify facade suite
  green at HEAD, proving these are safe read/navigation probes with no
  write-shaped path.

## Outcome

The verify and portal CLI commands are proven safe read/navigation probes.

Verification (re-run at HEAD 2026-07-10):

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_live_portals_verbs.py -q`
  passed (batched run: 34 passed with the notifications/justificante/iva/borrador
  suites); portal verbs open an AEAT URL only, no data mutation.
- `uv run --no-sync pytest src/aeat/application/live/tests/test_verify.py -q`
  passed (batched run: 18 passed with the registry/read-subgroup and IVA wallet
  suites); the verify facade is a read handshake probe.

## Notes

- Portal-open is a navigation probe with no AEAT data return, so there is no
  live-positive artefact to capture; the safe-probe / no-write-shaped contract is
  proven offline. Live verify handshake against AEAT is credential-gated and is
  carried forward with the curated live pytest lane (S28) and the operator
  manual sweep (S26).
