---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S73'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W09.P21.S73 constants inventory

Scope: Inventory AEAT/Sede executable literals outside the centralized settings, external constants, and registry surfaces.

## Description

- Ran the existing centralization tests for live Sede executable routes, auxiliary manual/oracle routes, and live browser action labels.
- Ran an AST inventory over non-test Python modules under `src/aeat`, excluding docstrings and the central external-constants module.
- Classified remaining matches by ownership surface instead of treating them as live-wallet blockers.

## Outcome

The existing centralization tests pass. The non-test executable inventory found 47 remaining route or host literals:

- 41 portal catalogue entries under `src/aeat/domain/portals/_entries`.
- 6 portal host enum literals under `src/aeat/domain/portals/_categories.py`.
- 1 portal metadata regex/error string under `src/aeat/domain/portals/_metadata.py`.
- 1 Cl@ve cancellation JavaScript snippet in `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` that embeds `ObtenerClaveMovil` in the script body.

The portal catalogue findings are registry-shaped metadata and belong to S74/S75 design under WALLET-041: either migrate them into a centralized TOML/YAML authority or explicitly declare the typed portal catalogue as the authoritative registry surface. The Cl@ve script-body finding should be reviewed under S74 because the route token is already centralized for navigation, but the in-page JavaScript still embeds the browser-global function name.

## Notes

No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
