---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
body_hash: 'sha256:660488b3cc2604bf142d554a2b4cec420c721a5ea2774c105afbbd0dbb4a079a'
step_id: 'S52'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename the secondary bundle manifest identity and executable

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Rename the secondary bundle identity, display copy, author, and keywords to Cadrumo.
- Hard-cut the MCP entry point and command to `cadrumo-mcp`, the product environment to `CADRUMO_MCP_PERSONA`, and product tools to `cadrumo_*` names.
- Retain AEAT only where it identifies the tax authority, BOE/AEAT legal corpus, or authority search keyword.

## Outcome

The secondary MCP bundle manifest now presents only the Cadrumo product identity
and executable contract, with no former command, tool alias, or fallback.

## Notes

- Re-execution followed the binding ADR's ratified convention: `Cadrumo` in
  sentence prose, machine identity `cadrumo`, product environment prefix
  `CADRUMO_`, human CLI `aeat`, and authority referent `AEAT`.
- The real project manifest checker reported `manifest.json valid: cadrumo 0.2.0`.
- Two manifest-focused MCPB build tests passed; later bundle-build and signing
  behavior remains assigned to S54.
- Completion audit found the root release had advanced to `0.2.1` while the MCPB
  manifest remained `0.2.0`. S52 was reopened and the manifest version was
  realigned to the root `pyproject.toml` authority without changing identity or
  prose fields.
- The existing live version-parity test required no duplication: the real
  manifest checker reported `manifest.json valid: cadrumo 0.2.1`; Ruff format,
  Ruff lint, Ty, and all six MCPB tests passed.
