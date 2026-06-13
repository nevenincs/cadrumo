---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S81'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# Wallet-Only Export Provenance Coverage

Scope: `src/aeat/application/modelo/_export.py`, `src/aeat/application/modelo/test_export.py`, `src/aeat/domain/calculations/registry`.

## Description

- Add redacted `ModeloIvaWalletDecisionProvenance` to the Modelo export result surface.
- Add export-event payload fields for Modelo 303 wallet authority, divergence, target period, and hash references only.
- Add tests proving taxpayer identifiers, wallet amounts, and raw source locators are absent from the exported wallet provenance payload.
- Preserve the limitation that S81 itself covered only redacted provenance helper surfaces; S85 later proved the full Modelo 303 `export_modelo_revision` happy path against the registry-backed export layout.

## Outcome

`S81` is complete for export provenance coverage. The full Modelo 303 export happy path was tracked separately and completed under `S85`.

## Notes

No live AEAT contact was made. No taxpayer values were added to fixtures. The coverage uses synthetic redaction sentinels and production domain decision models.
