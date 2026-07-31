---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S39'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Claude Desktop MCPB installed tax oracle

## Scope

- `.github/workflows/packaging-claude.yml`

## Description

- Built a clean version `0.2.1` MCPB cohort from source commit `11c82d2f030c1e75d6b34606e3373421c4f5bce5`.
- Validated and provisioned the exact MCPB through its bundled UV runtime before client installation.
- Updated Claude Desktop to `1.22209.0.0`, removed the retired local MCPB, and installed the exact replacement through the real client UI.
- Verified Claude recorded bundle SHA-256 `8615c66cc05441a8b60f82ccef7f5a1374af81dd37890acf03a6341c62f24cd2` and installed the exact root wheel SHA-256 `cac6c982a5be58006533214f3cf5d1340c6a45d92953995d573737b84199134d`.
- Enabled the extension and observed Claude Desktop connect and advertise 16 tools.
- Re-ran the client oracle against fresh, project-independent storage and created a new legal-entity profile.
- Executed Modelo 200 work creation and calculation through Claude Desktop using only installed Cadrumo MCP tools.
- Bound the client transcript, installed artifact hashes, telemetry hashes, legal references, and tax result in `claude-desktop-installed-tax-evidence.json`.

## Outcome

The manual Claude Desktop acceptance row passed. The installed MCPB performed the claimed tax operation from a clean state and persisted it across a client-side request timeout and MCP transport restart.

- Work unit: `3b5d0fba5a9499fa839262e278bd3184ee40fc5f35fa0632cd2749ffb9607604`
- Calculation revision: `f02161822acd30c1d776f6da214088bfc918659d25f633f90ccd5459d03fc250`
- Oracle: `DP200014:00562 = 23000.00`
- Formula: `modelo-200-cuota-integra`, resolved through `is.modelo-200.tipo-gravamen-pyme`
- Sources: `aeat-dr-200-2025` and `aeat-modelo-200-manual-2024`
- Notice: `modelo.work.calculate.plazo_vencido_unassessed_preview`

The extension created fresh encrypted local state outside any project folder. Claude's first work-creation request timed out at 60 seconds while the server completed in 63.684 seconds; after reconnecting and re-confirming identity, the retry returned the same work unit idempotently. The corrected calculation completed in 20.100 seconds and the casilla metadata lookup completed in 19.330 seconds.

## Notes

- S39 remains open because `.github/workflows/packaging-claude.yml` does not yet automate this client acceptance sequence.
- The first mutation was correctly refused until `cadrumo_whoami` confirmed the active taxpayer.
- Claude first passed keyed calculation inputs as objects; the product returned `REFUSED_CLI_BOUNDARY`, Claude corrected them to `ID=VALUE` arrays, and the calculation succeeded.
- The initial client run used persistent state and passed; the retained clean-state rerun is the primary acceptance evidence.
- The MCPB is unsigned, so no publisher-signature claim is approved.
- Acceptance covers Claude Desktop/Cowork on Windows only. It does not close the all-claimed-clients row or cross-platform matrix.
- The artifact still carries English-only human-facing MCP descriptions and the planned `cadrumo-` harness identity verification remains open under S69-S71.
