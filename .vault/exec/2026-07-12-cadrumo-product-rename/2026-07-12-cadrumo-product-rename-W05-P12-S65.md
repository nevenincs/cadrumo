---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S65'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update Catalan product locale messages through the locales CLI

## Scope

- `Catalan locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed Catalan-only production command `python -m cadrumo.locales canonicalize-product-identity --locale ca` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, raw residue classification, and live Catalan help output.

## Outcome

- The command changed exactly 39 semantic leaves: 26 command-leading references became `aeat`, and 13 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The Catalan catalogue hash changed from `9A6F5FE244A671515A6EB66E40817EAA918077791123342759708A1FD19FD12E` to `91573AD9E6529EF9BDFFE9BAB9B12593C7DA6DA8A221E5BF0654FD5FAFCD6888`.
- English, Spanish, and Hungarian hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live Catalan help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 169-insertion and 176-deletion textual diff; semantic comparison isolated the 39 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 231 occurrences and `CADRUMO_` remained at 21 occurrences.
- Raw Catalan residue is classified as 13 `CADRUMO` product displays, 21 `CADRUMO_*` settings, 225 `aeat` command prefixes, one `registry/aeat/treaties/` authority taxonomy path, 227 standalone `AEAT` authority references, and four `AEAT_*` authority settings.
- The only valid remaining lowercase `cadrumo` machine or historical residue is `cadrumo-vault/` in `cli.config.google.sync.calc.export_help`. No lowercase `cadrumo` setting, MCP executable, URI scheme, or companion namespace is present.
- English, Spanish, and Catalan targeted residue is zero. Remaining Hungarian display/command residue is 6/24 for S66.
- No locale YAML was hand-edited.
