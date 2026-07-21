---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S66'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update Hungarian product locale messages through the locales CLI

## Scope

- `Hungarian locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed Hungarian-only production command `python -m cadrumo.locales canonicalize-product-identity --locale hu` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, raw residue classification, and live Hungarian help output.

## Outcome

- The command changed exactly 28 semantic leaves: 22 command-bearing leaves contained 24 command-leading references that became `aeat`, and 6 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The Hungarian catalogue hash changed from `9BC8CEED6AB0E139003697D072CF2D93D3DA81CC698354C167036EDC10776655` to `4540D54CA3F0C6A65060ECC3629E0C82437E2FD40FCCF1987B1F9EE57335E1BF`.
- English, Spanish, and Catalan hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live Hungarian help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 133-insertion and 147-deletion textual diff; semantic comparison isolated the 28 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 226 occurrences and `CADRUMO_` remained at 20 occurrences.
- Raw Hungarian residue is classified as 6 `CADRUMO` product displays, 20 `CADRUMO_*` settings, 215 `aeat` command prefixes, one Hungarian prose reference to the `aeat` product CLI, one `registry/aeat/treaties/` authority path, 222 standalone `AEAT` authority references, and four `AEAT_*` authority settings.
- The valid remaining lowercase `cadrumo` residues are exactly `cadrumo_secret_store_backend` in `adapters.google.oauth_flow.suggestions.use_keyring_or_synthetic` and `cadrumo-vault/` in `cli.config.google.sync.calc.export_help`. No lowercase MCP executable, URI scheme, or companion namespace is present.
- Targeted title-case and command-leading residue is zero in all four catalogues.
- No locale YAML was hand-edited.
