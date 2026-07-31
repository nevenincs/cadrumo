---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:ccfd13f6a4962a69d3ba1a6f1183dcaa51a6941e186ebbcef3b41b3a8ac7e0ca'
step_id: 'S11'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add Modelo 145 registry TOML using only source-backed communication, validation, and export authority

## Scope

- `registry/aeat/modelos`

## Description

- Restore the Modelo 145 directory registry foundation with source-backed manifest, revision metadata, communication application links, casillas, and record-design parity.
- Ground the registry foundation in the accepted local payer-communication ADR and existing Modelo 145 AEAT/BOE source catalogue.
- Keep `export_layouts` absent so this step does not claim a completed fixed-width fichero implementation.

## Outcome

- The registry now declares Modelo 145 as an informative, ad-hoc local payer communication with one `2012-01-31-y-siguientes` revision.
- The revision carries 50 manual, source-backed casillas and one official `record_design_layout` parity reference to `aeat-dr-145-v20`.
- The previous broad registry-load blocker is closed: the focused registry authority gates load Modelo 145 without the prior zero-casilla or missing-workbook-parity validation errors.

## Notes

- This step did not register the fixed-width layout. `P03.S13` later added the grounded DR145 fixed-width layout.
